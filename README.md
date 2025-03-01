# AI-Scribe
A simple AI article writer that uses Google Gemini 2.0 and Grounded search to provides a short article with research.
A Streamlit-based web application that generates technical articles using the Google Gemini API. Users can input a topic, customize the audience, tone, and focus, and the app produces a well-structured HTML article with grounded content from Google Search.

## Features
Customizable Articles: Specify the topic, target audience (beginners, intermediate, experts), tone (casual, formal, technical), and specific focus areas.

* Dynamic Content: Leverages the Gemini API to generate sections, questions, and answers, grounded with Google Search results.

* HTML Output: Produces a professionally formatted HTML article with tables, lists, and links, styled with CSS.

* Interactive UI: Built with Streamlit for an easy-to-use browser interface.

* Rate Limiting: Implements request and token rate limiting to respect API constraints.

## Prerequisites
Python 3.8+: Ensure you have Python installed.

Gemini API Key: Obtain an API key from Google for the Gemini model (sign up via Google Cloud or relevant service).

GitHub Account: For deployment via Streamlit Community Cloud.

Installation
Clone the Repository:

    bash
    git clone https://github.com/yourusername/your-repo-name.git
    cd your-repo-name

Install Dependencies:
  ````bash pip install -r requirements.txt````

Run Locally:
  ````bash streamlit run article_writer.py````

Open your browser to ````http://localhost:8501```` and enter your Gemini API key when prompted.

## Usage
### **Launch the App:**
Run the app locally or access the deployed version (see Deployment section).

### **Input Details:**
* Gemini API Key: Enter your API key in the provided text field (kept secure, not stored in code).

* Topic: Specify the article topic (e.g., "Is AI important in Customer Service?").

* Audience: Choose the target audience (Beginners, Intermediate, Experts).

* Tone: Select the tone (Casual, Formal, Technical).

* Focus: Add specific details or examples to include (optional).

* Questions per Section: Set the number of questions (1-5) per article section.

* Generate Article: Click "Generate Article" and wait for the app to process (may take a few minutes due to API calls).

* View the HTML article in the browser and download the generated .html file from the app directory.

## Contributing
Contributions are welcome! Please:
* Fork the repository.

* Create a feature branch (git checkout -b feature/your-feature).

* Commit your changes (git commit -m "Add your feature").

* Push to the branch (git push origin feature/your-feature).

* Open a Pull Request.

## License
This is offered under a GPL 3.0 license

## Acknowledgments
* Built with Streamlit and Google Gemini API.
* Thanks to the open-source community for inspiration and tools.





