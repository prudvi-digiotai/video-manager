from utils import upload_file, PARENT_FOLDER_ID, send_email
from tools import generate_video
import nltk
from nltk.corpus import stopwords
from tools import extract_relevant_sections_from_website


class ResearchAgent():
    def __init__(self, llm, url, topic) -> None:
        self.llm = llm
        self.url = url
        self.topic = topic

        nltk.download('stopwords')
        self.stop_words = set(stopwords.words('english'))

    def select_keywords(self):

        core_terms = [term.strip().lower() for term in self.topic.split() if term.isalpha()]
        filtered_keywords = [keyword for keyword in core_terms if keyword.lower() not in self.stop_words and len(keyword) > 1]

        prompt = (
            f"Generate a list of relevant keywords related to the topic '{self.topic}'. "
            f"These keywords should help in filtering relevant content from a website. "
            f"Keywords from the topic are {filtered_keywords}. Remove useless and add newly generated. "
            f"Output format: A list of keywords, separated by commas."
        )
        response = self.llm.invoke(prompt)
        keywords = response.content.strip()

        keyword_list = [keyword.strip() for keyword in keywords.split(',') if keyword]

        filtered_keywords = [keyword for keyword in keyword_list if keyword.lower() not in self.stop_words and len(keyword) > 1]

        return filtered_keywords

    def scrape_relevant_content(self, keywords):
        try:
            content = extract_relevant_sections_from_website(self.url, keywords)
            return content
        except Exception as e:
            print(f"Error while scraping content: {e}")
            return {}

    def filter_content(self, scraped_content):
        prompt = (
            f"Given the topic '{self.topic}', evaluate the relevance of the following content. "
            f"Content is considered relevant if it partially or slightly related to the topic. "
            f"For each content piece, output 'yes' or 'no' based on this criterion.\n\n"
        )

        filtered_content = {}
        for url, text in scraped_content.items():
            full_prompt = f"{prompt}Content: {text}\n\nRelevance:"
            relevance = self.llm.invoke(full_prompt).content.strip()
            print(relevance, url)
            if "yes" in relevance.lower():
                filtered_content[url] = text

        return filtered_content


    def summarize_content(self, content):
        summarized_content = {}
        for url, text in content.items():
            prompt = (
                f"Summarize how the company contributes to or solves the topic '{self.topic}' using the extracted sections from their website({url}). "
                f"Expected Output: A comprehensive summary explaining the company's role in addressing the topic."
                f"\n{text}\n\nSummary:"
            )
            summary = self.llm.invoke(prompt).content
            summarized_content[url] = summary
        return summarized_content

    def research(self):
        keywords = self.select_keywords()
        print(f"Selected Keywords: {keywords}")
        
        if not keywords:
            print("No keywords generated, stopping research.")
            return {}
        
        scraped_content = self.scrape_relevant_content(keywords)
        print(f"Scraped Content: {scraped_content}")
        
        if not scraped_content:
            print("No content scraped, stopping research.")
            return {}

        filtered_content = self.filter_content(scraped_content)
        print(f"Filtered Content: {filtered_content}")
        
        if not filtered_content:
            print("No relevant content found, stopping research.")
            return {}

        summarized_content = self.summarize_content(filtered_content)
        print(f"Summarized Content: {summarized_content}")
        
        return summarized_content


class VideoAgent:
    def __init__(self, llm, topic, summary) -> None:
        self.llm = llm
        self.topic = topic
        self.summary = summary

    def generate_script(self):
        prompt = (
            "Generate a video script with two narration and image prompt pairs for the following topic, focusing on the company's expertise related to the topic. "
            "The script should contain around 200 words total. Start by explaining the topic and then highlight the company's role or expertise in relation to it. "
            "The Narration must start with topic name. "
            "Ensure that the image prompts do not include any text, names, logos, or other identifying features. "
            "Provide a descriptive image prompt that clearly defines elements, colors, and subjects. For instance, 'The sky was a crisp blue with green hues' is more descriptive than just 'blue sky'."
            f"\n\n**Topic:** \n{self.topic}\n\n"
            f"**Summary:** \n{self.summary}\n\n"
            "Expected Output: Two pairs of sentences. Enclose narration in <narration> narration here </narration> tags and image prompts in <image> image prompt here </image> tags."
        )

        script = self.llm.invoke(prompt).content.strip()
        return script
    
    def upload_to_drive(self, video_file_path):
        video_id = upload_file(video_file_path, 'video', PARENT_FOLDER_ID)
        video_link = f"https://drive.google.com/file/d/{video_id}/view?usp=sharing"
        video_status = f'Video generated, link to video: {video_link}'
        return video_status
    
    def create_video(self):
        script = self.generate_script()
        video_path = generate_video(script, self.topic, True)
        akg = self.upload_to_drive(video_path)
        return akg

class EmailAgent:
    def __init__(self, llm, to_mail):
        self.llm = llm
        self.to_mail = to_mail

    def write_email(self, name, video_status=None):
        email_body_template = (
            f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; margin: 0; padding: 20px;">
                    <div style="max-width: 600px; margin: auto; background-color: #ffffff; border-radius: 8px; padding: 20px; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);">
                        <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eeeeee;">
                            <h1 style="color: #333333; margin: 0;">Social Media Manager</h1>
                        </div>
                        <div style="padding: 20px;">
                            <p style="font-size: 16px; color: #333333;">Hello {name},</p>
                            <p style="font-size: 16px; color: #555555;">We’re excited to share your latest updates with you. Here’s a summary of what we’ve prepared:</p>

                            <div style="margin-top: 20px;">
                                <h3 style="color: #007BFF; font-size: 18px;">Video Update</h3>
                                <p style="font-size: 16px; color: #555555;">{video_status or 'No video content available.'}</p>
                            </div>

                        </div>
                        <div style="padding-top: 20px; border-top: 1px solid #eeeeee; text-align: center;">
                            <p style="font-size: 16px; color: #555555; margin: 0;">Thank you for using our service!</p>
                            <p style="font-size: 16px; color: #555555; margin: 0;">Best regards,<br>Your Content Team</p>
                        </div>
                    </div>
                </body>
            </html>
            """
        )
        return email_body_template

    def send_email(self, name, video_status=None):
        name = name.split('@')[0]
        email_body = self.write_email(name, video_status)
        subject = "Your Generated Content Update"
        send_email(self.to_mail, subject, email_body)
        return f"Email sent to {self.to_mail}!"
