# AI Real Estate Agent Team (Bangladesh)

A multi-agent AI system for property search, market analysis, and valuation in the Bangladeshi real estate market.

## Features
- 🔍 **Property Search Agent**: Scrapes listings from top Bangladeshi websites (Bproperty, Bdhousing, Bestbari, Aabason, Apexproperty, TheTolet) using Firecrawl
- 📊 **Market Analysis Agent**: Provides insights on market trends and investment potential
- 💰 **Property Valuation Agent**: Evaluates fair pricing and investment opportunities
- 🏠 **Professional UI**: Clean, responsive interface built with Streamlit
- 🔄 **Flexible Search**: Supports both buying and renting for various property types (House, Office, Flat, Land, etc.)

## Tech Stack
- **Frontend**: Streamlit
- **Backend**: Python, Agno Agent Framework
- **LLM**: Google Gemini
- **Web Scraping**: Firecrawl
- **Data Modeling**: Pydantic
- **Deployment**: Streamlit Cloud

## Getting Started

### 1. Set up API Keys
1. Get your Google AI API Key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Get your Firecrawl API Key from [Firecrawl.dev](https://firecrawl.dev)
3. Create a `.env` file with your keys

### 2. Run Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py