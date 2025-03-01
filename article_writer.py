import subprocess
try:
    from google import genai
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Part
    import os
    from bs4 import BeautifulSoup
    import requests
    import nltk
    from nltk.tokenize import word_tokenize
    import re
    import html
    import textstat
    import json
    from jinja2 import Environment, FileSystemLoader
    from datetime import datetime
    import streamlit as st
    print("All libraries already installed")
except ImportError:
    print("Installing required libraries")
    subprocess.check_call(["pip", "install", "google-genai", "textstat", "streamlit", "jinja2"])
    from google import genai
    from google.genai.types import Tool, GenerateContentConfig, GoogleSearch, Part
    import os
    from bs4 import BeautifulSoup
    import requests
    import nltk
    from nltk.tokenize import word_tokenize
    import re
    import html
    import textstat
    import json
    import streamlit as st
    from jinja2 import Environment, FileSystemLoader
    print("Libraries Installed")
try:
    nltk.data.find('tokenizers/punkt')
    print("NLTK punkt tokenizer already downloaded")
except LookupError:
    nltk.download('punkt')
    print("NLTK punkt tokenizer downloaded")

import time
from collections import deque

# --- Rate Limiting Constants ---
REQUESTS_PER_MINUTE = 15
TOKENS_PER_MINUTE = 1_000_000
REQUESTS_PER_DAY = 1500
MINUTE = 60
DAY = 24 * 60 * 60

# --- Rate Limiting Data Structures ---
request_timestamps_minute = deque()
token_timestamps_minute = deque()
request_timestamps_day = deque()

# Model ID (no API key hardcoded)
model_id = "gemini-2.0-flash"  # Adjust if needed based on available models

def rate_limit(prompt: str = ""):
    current_time = time.time()
    while request_timestamps_minute and current_time - request_timestamps_minute[0] > MINUTE:
        request_timestamps_minute.popleft()
    if len(request_timestamps_minute) >= REQUESTS_PER_MINUTE:
        sleep_time = MINUTE - (current_time - request_timestamps_minute[0])
        print(f"RPM Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
        time.sleep(sleep_time)
    request_timestamps_minute.append(current_time)

    token_count = len(prompt.split())
    while token_timestamps_minute and current_time - token_timestamps_minute[0][0] > MINUTE:
        token_timestamps_minute.popleft()
    total_tokens_this_minute = sum(tokens for _, tokens in token_timestamps_minute) + token_count
    if total_tokens_this_minute > TOKENS_PER_MINUTE:
        sleep_time = MINUTE - (current_time - token_timestamps_minute[0][0])
        print(f"TPM Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
        time.sleep(sleep_time)
    token_timestamps_minute.append((current_time, token_count))

    while request_timestamps_day and current_time - request_timestamps_day[0] > DAY:
        request_timestamps_day.popleft()
    if len(request_timestamps_day) >= REQUESTS_PER_DAY:
        sleep_time = DAY - (current_time - request_timestamps_day[0])
        print(f"RPD Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
        time.sleep(sleep_time)
    request_timestamps_day.append(current_time)

def safe_generate_content(client, *args, **kwargs):
    prompt = ""
    if 'contents' in kwargs:
        if isinstance(kwargs['contents'], str):
            prompt = kwargs['contents']
        elif isinstance(kwargs['contents'], list):
            prompt_parts = []
            for item in kwargs['contents']:
                if isinstance(item, str):
                    prompt_parts.append(item)
                elif isinstance(item, Part) and hasattr(item, 'text'):
                    prompt_parts.append(item.text)
                elif isinstance(item, dict) and 'text' in item:
                    prompt_parts.append(item['text'])
                elif hasattr(item, '__str__'):
                    prompt_parts.append(str(item))
            prompt = " ".join(prompt_parts)
    rate_limit(prompt)
    return client.models.generate_content(*args, **kwargs)

def generate_section_prompts(client, topic):
    prompt = (
        f"You are an expert in writing technical articles for a junior audience. Given the topic '{topic}', "
        f"generate a dictionary of 5-7 section names and descriptions. Use snake_case keys (e.g., 'introduction') "
        f"and brief descriptions as values. Output in valid JSON format with no trailing commas or comments."
    )
    response = safe_generate_content(client, model=model_id, contents=prompt)
    
    try:
        text = response.text.strip()
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            raise ValueError("No JSON found")
        
        json_string = json_match.group(0)
        json_string = re.sub(r',\s*}', '}', json_string)
        section_prompts = json.loads(json_string)
        
        if not isinstance(section_prompts, dict):
            raise ValueError("Not a dictionary")
        
        return section_prompts
    except Exception as e:
        print(f"Error decoding JSON: {e}. Falling back to defaults.")
        return {
            "introduction": "An introduction to the topic.",
            "background": "Background information on the topic.",
            "main_points": "The main technical points, with examples.",
            "examples": "Real-world examples illustrating the key concepts.",
            "conclusion": "A conclusion summarizing the article."
        }

def generate_questions(client, topic, section, num_questions, existing_questions):
    prompt = (
        f"You are a technical expert writing for a junior audience. "
        f"For an article titled '{topic}', generate {num_questions + 2} unique questions for the section '{section}'. "
        f"Avoid these existing questions: {', '.join(existing_questions)}. "
        f"Return only the questions, one per line."
    )
    response = safe_generate_content(client, model=model_id, contents=prompt)
    questions = [q.strip() for q in response.text.split("\n") if q.strip()]
    unique_questions = []
    for q in questions:
        q_lower = q.lower()
        if q_lower not in existing_questions and len(unique_questions) < num_questions:
            unique_questions.append(q)
            existing_questions.add(q_lower)
    return unique_questions

def search_and_ground(client, questions):
    grounded_answers = {}
    google_search_tool = Tool(google_search=GoogleSearch())
    for question in questions:
        part = Part()
        part.text = question
        response = safe_generate_content(
            client,
            model=model_id,
            contents=[part],
            config=GenerateContentConfig(
                tools=[google_search_tool],
                response_modalities=["TEXT"],
            ),
        )
        answer = ""
        urls = []
        if response.candidates and response.candidates[0].content.parts:
            for p in response.candidates[0].content.parts:
                answer += p.text
        if (response.candidates and response.candidates[0].grounding_metadata and 
            hasattr(response.candidates[0].grounding_metadata, "search_entry_point") and 
            hasattr(response.candidates[0].grounding_metadata.search_entry_point, "rendered_content")):
            urls = [response.candidates[0].grounding_metadata.search_entry_point.rendered_content]
        grounded_answers[question] = {"answer": answer, "urls": urls}
    return grounded_answers

def generate_article_section(grounded_answers, questions):
    article_body = ""
    for question in questions:
        answer = grounded_answers.get(question, {}).get("answer", "")
        urls = grounded_answers.get(question, {}).get("urls", [])
        
        article_body += f"### {question}\n\n{answer}\n\n"
        if urls:
            article_body += f"*Sources:* {', '.join(urls)}\n\n"
    return article_body

def generate_article_conclusion(client, article_body):
    prompt = (
        f"You are an experienced technical writer who explains complex subjects to juniors. "
        f"Given the main body of an article: {article_body}, write a conclusion that "
        f"summarizes the key ideas, clarifies technical concepts with examples, and maintains an authoritative tone. "
        f"Format your response as valid HTML with proper paragraph tags. Do not use Markdown formatting."
    )
    response = safe_generate_content(client, model=model_id, contents=prompt)
    conclusion = response.text.strip()
    if not conclusion.lower().startswith('<'):
        conclusion = f"<p>{conclusion}</p>"
    return conclusion

def convert_article_to_html(client, topic, sections_text):
    prompt = (
        f"You are an expert in HTML formatting. Convert the following article content into valid, well-structured HTML. "
        f"Ensure proper use of <h1> for the title, <h2> for section titles, <h3> for questions, <p> for paragraphs, "
        f"<table> for any tabular data (detect tables from text like rows with consistent separators), "
        f"<ul> or <ol> for lists, and <a> tags for URLs. Use semantic HTML and avoid Markdown. "
        f"Wrap each section in a <section> tag with an appropriate id. Here’s the article:\n\n"
        f"# {topic}\n\n{sections_text}"
    )
    response = safe_generate_content(client, model=model_id, contents=prompt)
    html_content = response.text.strip()
    if not html_content.lower().startswith('<'):
        html_content = f"<section><p>{html_content}</p></section>"
    return html_content

def compile_html_with_jinja(topic, sections, template_dir="templates", template_file="article_template.html"):
    try:
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template(template_file)
        rendered_html = template.render(
            topic=topic,
            article_content=sections["content"],
            current_date=datetime.now().strftime("%Y-%m-%d")
        )
    except Exception as e:
        print(f"Error rendering template: {e}. Using fallback HTML.")
        rendered_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{html.escape(topic)}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        h1 {{ font-size: 28px; margin-bottom: 20px; }}
        h2 {{ font-size: 24px; margin-top: 30px; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
        h3 {{ font-size: 20px; margin-top: 25px; margin-bottom: 10px; color: #444; }}
        p {{ margin-bottom: 15px; }}
        .sources {{ font-size: 0.9em; color: #666; margin-top: 5px; margin-bottom: 20px; }}
        code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; font-family: monospace; }}
        section {{ margin-bottom: 40px; }}
        ul, ol {{ margin-bottom: 15px; padding-left: 30px; }}
    </style>
</head>
<body>
    {sections["content"]}
</body>
</html>"""
    return rendered_html

def generate_and_save_article(client, topic, num_questions=3):
    section_prompts = generate_section_prompts(client, topic)
    sections_text = ""
    all_questions = set()
    
    for section_id, section_description in section_prompts.items():
        if section_id == "conclusion":
            continue
            
        questions = generate_questions(client, topic, section_description, num_questions=num_questions, existing_questions=all_questions)
        grounded_answers = search_and_ground(client, questions)
        section_title = section_id.replace('_', ' ').title()
        sections_text += f"## {section_title}\n\n{generate_article_section(grounded_answers, questions)}"
    
    conclusion_text = generate_article_conclusion(client, sections_text)
    sections_text += f"## Conclusion\n\n{conclusion_text}\n"
    
    final_html_content = convert_article_to_html(client, topic, sections_text)
    final_html = compile_html_with_jinja(topic, {"content": final_html_content})
    
    clean_topic = re.sub(r'\W+', '', topic)
    filename = f"{clean_topic}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"Final article written to {filename}")
    return final_html

def run_streamlit_app():
    st.title("AI Article Generator")
    st.write("Generate a custom article with AI. Provide your Gemini API key and details to tailor the content.")

    # API Key input
    api_key = st.text_input("Enter your Gemini API Key:", type="password")
    
    if not api_key:
        st.warning("Please enter your Gemini API key to proceed.")
        return

    # Initialize Gemini client with the provided API key
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Invalid API key or connection issue: {e}")
        return

    # Topic input
    topic = st.text_input("Enter the article topic:", "Is AI important in Customer Service?")
    
    # Additional customization
    audience = st.selectbox("Target audience:", ["Beginners", "Intermediate", "Experts"], index=0)
    tone = st.selectbox("Tone of the article:", ["Casual", "Formal", "Technical"], index=2)
    focus = st.text_area("Specific focus or details to include (e.g., examples, industries, technologies):", "")
    num_questions = st.number_input("Number of questions per section:", min_value=1, max_value=5, value=3, step=1)

    if st.button("Generate Article"):
        if not topic:
            st.error("Please enter a topic.")
            return

        with st.spinner("Generating article... This may take a few minutes."):
            try:
                # Customize prompts based on user input
                custom_section_prompt = (
                    f"You are an expert in writing articles for a {audience.lower()} audience. Given the topic '{topic}', "
                    f"generate a dictionary of 5-7 section names and descriptions in JSON format. "
                    f"The tone should be {tone.lower()}. Include {focus} in the content where relevant."
                )
                
                # Override generate_section_prompts to use custom prompt and accept client
                def custom_generate_section_prompts(client, topic):  # Add client parameter
                    response = safe_generate_content(client, model=model_id, contents=custom_section_prompt)
                    try:
                        json_string = re.search(r'\{[\s\S]*\}', response.text).group(0)
                        return json.loads(json_string)
                    except Exception as e:
                        print(f"Error decoding JSON: {e}. Using defaults.")
                        return {
                            "introduction": "An introduction to the topic.",
                            "background": "Background information on the topic.",
                            "main_points": "The main technical points, with examples.",
                            "examples": "Real-world examples illustrating the key concepts.",
                            "conclusion": "A conclusion summarizing the article."
                        }

                # Override generate_questions with custom details and accept client
                def custom_generate_questions(client, topic, section, num_questions, existing_questions):  # Add client parameter
                    prompt = (
                        f"You are a technical expert writing for a {audience.lower()} audience. "
                        f"For an article titled '{topic}', generate {num_questions + 2} unique questions for the section '{section}'. "
                        f"Use a {tone.lower()} tone and incorporate {focus} where applicable. "
                        f"Avoid these existing questions: {', '.join(existing_questions)}. "
                        f"Return only the questions, one per line."
                    )
                    response = safe_generate_content(client, model=model_id, contents=prompt)
                    questions = [q.strip() for q in response.text.split("\n") if q.strip()]
                    unique_questions = []
                    for q in questions:
                        q_lower = q.lower()
                        if q_lower not in existing_questions and len(unique_questions) < num_questions:
                            unique_questions.append(q)
                            existing_questions.add(q_lower)
                    return unique_questions

                # Monkey-patch the original functions
                global generate_section_prompts, generate_questions
                generate_section_prompts = lambda client, topic: custom_generate_section_prompts(client, topic)
                generate_questions = lambda client, topic, section, num_questions, existing_questions: custom_generate_questions(client, topic, section, num_questions, existing_questions or set())

                # Generate article
                output_html = generate_and_save_article(client, topic, num_questions=num_questions)
                st.success("Article generated successfully!")
                st.markdown(output_html, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"An error occurred: {e}")
                
if __name__ == "__main__":
    run_streamlit_app()