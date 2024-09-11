from pydub import AudioSegment
from groq import Groq
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, ImageClip
import requests
import os
import tempfile
import re
import cv2
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from openai import OpenAI
from bs4 import BeautifulSoup
from langchain_community.document_loaders import YoutubeLoader

def extract_sections(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    sections = []
    for link in soup.find_all('a', href=True):
        sections.append({
            'text': link.get_text().strip(),
            'url': link['href']
        })
        
    return sections

def filter_relevant_sections(sections, keywords):
    relevant_sections = []
    for section in sections:
        if any(keyword.lower() in section['text'].lower() for keyword in keywords):
            relevant_sections.append(section)
    
    return relevant_sections

def filter_youtube_links(sections, keywords):
    youtube_sections = []
    for section in sections:
        if 'youtube' not in section['url']:
            sections.remove()

def gather_info_from_sections(relevant_sections):
    content = {}
    for section in relevant_sections:
        try:
            response = requests.get(section['url'])
            soup = BeautifulSoup(response.content, 'html.parser')
            clean_text = clean_scraped_text(soup.get_text())
            content[section['url']] = clean_text
        except Exception as e:
            print(e)
    
    return content

def clean_scraped_text(text):
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)

    patterns = [
        r'Home\s+About Us.*?\s+Contact Us',
        r'This website uses cookies.*?Privacy & Cookies Policy',  
        r'Copyright.*?Powered by.*',  
    ]

    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r'\|.*?\|', '', text)  
    text = text.strip()  

    return text

def youtube_transcript_loader(url):
    try:
        loader = YoutubeLoader.from_youtube_url(
            url, add_video_info=False
        )
        transcript = loader.load()[0]
        return transcript.page_content
    except Exception as e:
        print(e)
    
def gather_youtube_data(sections, keywords):
    youtube_sections = []
    for i, section in enumerate(sections):
        if 'youtube' in section['url']:
            youtube_sections.append(section)

    content = {}
    for section in youtube_sections:
        text = youtube_transcript_loader(section['url'])
        if text is not None:
            content[section['url']] = text

    relevant_content = {}
    for k, v in content.items():
        if any(keyword.lower() in v.lower() for keyword in keywords):
            relevant_content[k] = v

    return relevant_content

def extract_relevant_sections_from_website(website_url, keywords):
    sections = extract_sections(website_url)
    filtered_sections = filter_relevant_sections(sections, keywords)
    gathered_info = gather_info_from_sections(filtered_sections)
    youtube_info = gather_youtube_data(sections, keywords)
    total_info = gathered_info | youtube_info
    refined_info = {url: text for url, text in total_info.items() if len(text) > 200}  # Example threshold for content length

    return refined_info

def process_script(script):
    """Used to process the script into dictionary format"""
    dict = {}
    text_for_image_generation = re.findall(r'<image>(.*?)</?image>', script, re.DOTALL)
    text_for_speech_generation = re.findall(r'<narration>(.*?)</?narration>', script, re.DOTALL)
    dict['text_for_image_generation'] = text_for_image_generation
    dict['text_for_speech_generation'] = text_for_speech_generation
    return dict

def generate_speech(text, lang='en', speed=1.0, num=0):
    """
    Generates speech for the given script using gTTS and adjusts the speed.
    """
    temp_speech_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
    temp_speech_path = temp_speech_file.name

    
    client = OpenAI()

    speech_file_path = temp_speech_path
    response = client.audio.speech.create(
    model="tts-1",
    voice="echo",
    input= text
    )

    response.stream_to_file(speech_file_path)

    # tts = gTTS(text=text, lang=lang)
    # tts.save(temp_speech_path)

    sound = AudioSegment.from_file(temp_speech_path)
    if speed != 1.0:
        sound_with_altered_speed = sound._spawn(sound.raw_data, overrides={
            "frame_rate": int(sound.frame_rate * speed)
        }).set_frame_rate(sound.frame_rate)
        sound_with_altered_speed.export(temp_speech_path, format="mp3")
    else:
        sound.export(temp_speech_path, format="mp3")

    temp_speech_file.close()
    return temp_speech_path

def image_generator(script):
    """Generates images for the given script.
    Saves it to a temporary directory and returns the path.
    Args:
    script: a complete script containing narrations and image descriptions."""

    # remove_temp_files('/tmp')
    
    images_dir = tempfile.mkdtemp()

    client = OpenAI()
    dict = process_script(script)
    for i, text in enumerate(dict['text_for_image_generation']):
        try:
            response = client.images.generate(
                model="dall-e-2",
                prompt=text,
                size="512x512",
                quality="standard",
                n=1
            )
            image_url = response.data[0].url

            print(f'image {i} generated')
            # Download the image
            image_response = requests.get(image_url)
            if image_response.status_code == 200:
                with open(os.path.join(images_dir, f'image_{i}.png'), 'wb') as file:
                    file.write(image_response.content)
            else:
                raise Exception(f"Failed to download image with status code {image_response.status_code} and message: {image_response.text}")

        except Exception as e:
            raise Exception(f"Image generation failed: {e}")

    return images_dir

def speech_generator(script):
    """
    Generates speech files for the given script using gTTS.
    Saves them to a temporary directory and returns the path.
    Args:
    script: a complete script containing narrations and image descriptions.
    """
    speeches_dir = tempfile.mkdtemp()

    dict = process_script(script)
    for i, text in enumerate(dict['text_for_speech_generation']):
        speech_path = generate_speech(text, num=i)
        print(f'speech {i} generated')
        os.rename(speech_path, os.path.join(speeches_dir, f'speech_{i}.mp3'))

    return speeches_dir, dict['text_for_speech_generation']

def split_text_into_chunks(text, chunk_size):
    words = text.split()
    return [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

def add_text_to_video(input_video, text, duration=1, fontsize=40, fontcolor=(255, 255, 255),
                      outline_thickness=2, outline_color=(0, 0, 0), delay_between_chunks=0.3,
                      font_path='Montserrat-Bold.ttf'):
    temp_output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    output_video = temp_output_file.name

    chunks = split_text_into_chunks(text, 3)  # Adjust chunk size as needed

    cap = cv2.VideoCapture(input_video)
    if not cap.isOpened():
        raise ValueError("Error opening video file.")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    chunk_duration_frames = duration * fps
    delay_frames = int(delay_between_chunks * fps)

    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font file not found: {font_path}")

    try:
        font = ImageFont.truetype(font_path, fontsize)
    except Exception as e:
        raise RuntimeError(f"Error loading font: {e}")

    current_frame = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(frame_pil)

        chunk_index = current_frame // (chunk_duration_frames + delay_frames)

        if current_frame % (chunk_duration_frames + delay_frames) < chunk_duration_frames and chunk_index < len(chunks):
            chunk = chunks[chunk_index]
            text_bbox = draw.textbbox((0, 0), chunk, font=font)
            text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            text_x = (width - text_width) // 2
            text_y = height - 100  # Position text at the bottom

            if text_width > width:
                words = chunk.split()
                half = len(words) // 2
                line1 = ' '.join(words[:half])
                line2 = ' '.join(words[half:])

                text_size_line1 = draw.textsize(line1, font=font)
                text_size_line2 = draw.textsize(line2, font=font)
                text_x_line1 = (width - text_size_line1[0]) // 2
                text_x_line2 = (width - text_size_line2[0]) // 2
                text_y = height - 250 - text_size_line1[1]  # Adjust vertical position for two lines

                for dx in range(-outline_thickness, outline_thickness + 1):
                    for dy in range(-outline_thickness, outline_thickness + 1):
                        if dx != 0 or dy != 0:
                            draw.text((text_x_line1 + dx, text_y + dy), line1, font=font, fill=outline_color)
                            draw.text((text_x_line2 + dx, text_y + text_size_line1[1] + dy), line2, font=font, fill=outline_color)
                
                draw.text((text_x_line1, text_y), line1, font=font, fill=fontcolor)
                draw.text((text_x_line2, text_y + text_size_line1[1]), line2, font=font, fill=fontcolor)

            else:
                for dx in range(-outline_thickness, outline_thickness + 1):
                    for dy in range(-outline_thickness, outline_thickness + 1):
                        if dx != 0 or dy != 0:
                            draw.text((text_x + dx, text_y + dy), chunk, font=font, fill=outline_color)
                
                draw.text((text_x, text_y), chunk, font=font, fill=fontcolor)

            frame = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)

        out.write(frame)
        current_frame += 1

        # Ensure loop breaks after processing all frames
        if current_frame >= frame_count:
            break

    cap.release()
    out.release()
    # cv2.destroyAllWindows()
    
    return output_video

def apply_zoom_in_effect(clip, zoom_factor=1.2):
    width, height = clip.size
    duration = clip.duration

    def zoom_in_effect(get_frame, t):
        frame = get_frame(t)
        zoom = 1 + (zoom_factor - 1) * (t / duration)
        new_width, new_height = int(width * zoom), int(height * zoom)
        resized_frame = cv2.resize(frame, (new_width, new_height))
        
        x_start = (new_width - width) // 2
        y_start = (new_height - height) // 2
        cropped_frame = resized_frame[y_start:y_start + height, x_start:x_start + width]
        
        return cropped_frame

    return clip.fl(zoom_in_effect, apply_to=['mask'])

def create_video_from_images_and_audio(images_dir, speeches_dir, final_video_filename, all_captions):
    """Creates video using images and audios.
    Args:
    images_dir: path to images folder
    speeches_dir: path to speeches folder
    final_video_filename: the topic name which will be used as final video file name"""
    print('hi')
    client = Groq(api_key='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')
    # images_paths = sorted(os.listdir(images_dir))
    # audio_paths = sorted(os.listdir(speeches_dir))
    images_paths = sorted([os.path.join(images_dir, img) for img in os.listdir(images_dir) if img.endswith('.png') or img.endswith('.jpg')])
    audio_paths = sorted([os.path.join(speeches_dir, speech) for speech in os.listdir(speeches_dir) if speech.endswith('.mp3')])
    clips = []
    temp_files = []
    temp_folder = tempfile.gettempdir()
    
    for i in range(min(len(images_paths), len(audio_paths))):
        img_clip = ImageClip(os.path.join(images_dir, images_paths[i]))
        audioclip = AudioFileClip(os.path.join(speeches_dir, audio_paths[i]))
        videoclip = img_clip.set_duration(audioclip.duration)
        zoomed_clip = apply_zoom_in_effect(videoclip, 1.3)
        
        # with open(os.path.join(speeches_dir, audio_paths[i]), "rb") as file:
        #     transcription = client.audio.transcriptions.create(
        #         file=(audio_paths[i], file.read()),
        #         model="whisper-large-v3",
        #         response_format="verbose_json",
        #     )
        #     caption = transcription.text
        temp_video_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4').name
        zoomed_clip.write_videofile(temp_video_path, codec='libx264', fps=24)
        temp_files.append(temp_video_path)
        
        caption = all_captions[i]
        final_video_path = add_text_to_video(temp_video_path, caption, duration=1, fontsize=20)
        temp_files.append(final_video_path)
        
        final_clip = VideoFileClip(final_video_path)
        final_clip = final_clip.set_audio(audioclip)

        print(f'create small video {i}')
        clips.append(final_clip)
    
    final_clip = concatenate_videoclips(clips)
    # if not final_video_filename.endswith('.mp4'):
    #     final_video_filename = final_video_filename + '.mp4'
    video_file_path = os.path.join(temp_folder, 'video.mp4')
    if os.path.exists(video_file_path):
        os.remove(video_file_path)
    final_clip.write_videofile(video_file_path, codec='libx264', fps=24)
    
    # Close all video files properly
    for clip in clips:
        clip.close()

    print(video_file_path)
    
    return video_file_path#os.path.join(video_dir, final_video_filename)

def process_pairs(pairs):
    """Used to process the script into dictionary format"""
    dict = {}
    text_for_image_generation = re.findall(r'<image_path>(.*?)</?image_path>', pairs, re.DOTALL)
    dict['img_pairs'] = text_for_image_generation
    return dict

def image_dir_generator(pairs):

    images_dir = tempfile.mkdtemp()

    dict = process_pairs(pairs)
    print(dict)
    for i, text in enumerate(dict['img_pairs']):
        with open(text, 'rb') as f:
            image = f.read()
        with open(os.path.join(images_dir, f'image_{i}.png'), 'wb') as file:
            file.write(image)

    return images_dir
# @tool
def generate_video(pairs, final_video_filename, is_ai_img):
    """ Generates video using narration and image prompt pairs.

    Args:
        pairs:A string of arration and image prompt pairs enclosed in <narration> and <image> tags.
        final_video_filename: the topic name which will be used as final video file name

    Returns:
        Generated video path"""

    if is_ai_img:
        images_dir = image_generator(pairs)
    else:
        images_dir = image_dir_generator(pairs)
    print(images_dir)
    speeches_dir, all_captions = speech_generator(pairs)
    print(speeches_dir)
    video_path = create_video_from_images_and_audio(images_dir, speeches_dir, final_video_filename, all_captions)
    print('video', video_path)

    return video_path
