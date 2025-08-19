import os
import streamlit as st
import json
import time
import re
from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from pydantic import BaseModel, Field
from typing import List, Optional

# Load environment variables
load_dotenv()

# API keys - must be set in environment variables
DEFAULT_GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DEFAULT_FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

# Pydantic schemas - updated for Bangladeshi property market
class PropertyDetails(BaseModel):
    address: str = Field(description="Full property address in Bangladesh")
    price: Optional[str] = Field(description="Property price in BDT")
    bedrooms: Optional[str] = Field(description="Number of bedrooms (e.g., '3 বেডরুম')")
    bathrooms: Optional[str] = Field(description="Number of bathrooms")
    area: Optional[str] = Field(description="Property area in katha/sft (e.g., '1200 sft' or '5 katha')")
    property_type: Optional[str] = Field(description="Type of property (e.g., 'ফ্ল্যাট', 'জমি', 'বাড়ি')")
    location_type: Optional[str] = Field(description="Location type (e.g., 'সিটি কর্পোরেশন', 'উপজেলা')")
    description: Optional[str] = Field(description="Property description in Bengali/English")
    features: Optional[List[str]] = Field(description="Property features (e.g., 'সুরক্ষিত এলাকা', 'পার্কিং স্থান')")
    images: Optional[List[str]] = Field(description="Property image URLs")
    contact_info: Optional[str] = Field(description="Seller/agent contact information with phone number")
    listing_url: Optional[str] = Field(description="Original listing URL")
    negotiable: Optional[bool] = Field(description="Whether price is negotiable")
    amenities: Optional[List[str]] = Field(description="Property amenities (e.g., 'লিফ্ট', 'সুইমিং পুল')")

class PropertyListing(BaseModel):
    properties: List[PropertyDetails] = Field(description="List of properties found in Bangladesh")
    total_count: int = Field(description="Total number of properties found")
    source_website: str = Field(description="Bangladeshi property website where properties were found")

class BangladeshiPropertyAgent:
    """Agent with direct Firecrawl integration for Bangladeshi property search"""
    
    def __init__(self, firecrawl_api_key: str, google_api_key: str, model_id: str = "gemini-2.5-flash"):
        self.agent = Agent(
            model=Gemini(id=model_id, api_key=google_api_key),
            markdown=True,
            description="I am a Bangladeshi real estate expert who helps find and analyze properties based on user preferences in Bangladesh."
        )
        self.firecrawl = FirecrawlApp(api_key=firecrawl_api_key)
        
        # Bangladeshi location mappings
        self.divisions = {
            "dhaka": ["dhaka", "gazipur", "narayanganj", "tangail", "manikganj"],
            "chattogram": ["chittagong", "chattogram", "coxsbazar", "cumilla", "feni"],
            "khulna": ["khulna", "bagerhat", "jessore", "kushtia"],
            "rajshahi": ["rajshahi", "natore", "pabna", "bogura"],
            "sylhet": ["sylhet", "moulvibazar", "sunamganj"],
            "barishal": ["barishal", "bhola", "patuakhali"],
            "rangpur": ["rangpur", "dinajpur", "thakurgaon"],
            "mymensingh": ["mymensingh", "jamalpur", "netrokona"]
        }

    def _format_bangladeshi_location(self, city: str, area: str = "") -> str:
        """Format location for Bangladeshi property sites"""
        city = city.lower().strip()
        area = area.lower().strip() if area else ""
        
        # Handle common Bangladeshi city name variations
        city_mapping = {
            "dhaka": "dhaka",
            "daka": "dhaka",
            "ঢাকা": "dhaka",
            "chittagong": "chittagong",
            "chattogram": "chittagong",
            "চট্টগ্রাম": "chittagong",
            "khulna": "khulna",
            "রাজশাহী": "rajshahi",
            "rajshahi": "rajshahi",
            "রংপুর": "rangpur",
            "rangpur": "rangpur",
            "সিলেট": "sylhet",
            "sylhet": "sylhet",
            "বরিশাল": "barisal",
            "barisal": "barisal",
            "খুলনা": "khulna"
        }
        
        # Map to standard English spelling
        city = city_mapping.get(city, city)
        area = city_mapping.get(area, area)
        
        # Format for URL
        if area:
            return f"{city}/{area}"
        return city

    def find_properties_direct(self, city: str, area: str, user_criteria: dict, selected_websites: list) -> dict:
        """Direct Firecrawl integration for Bangladeshi property search"""
        # Format location for Bangladeshi sites
        location = self._format_bangladeshi_location(city, area)
        
        # Create URLs for selected Bangladeshi property websites
        search_urls = {
            "Bikroy.com": f"https://www.bikroy.com/bn/ads/{location}/properties",
            "Bproperty.com": f"https://www.bproperty.com/en/{location}/properties-for-sale/",
            "AmarBari.com": f"https://www.amarbari.com/{location}/",
            "Bdproperty.com": f"https://www.bdproperty.com/{location}/properties/",
            "Chaldal Property": f"https://property.chaldal.com/{location}",
            "ShareBazar": f"https://www.sharebazar.com.bd/{location}/properties"
        }
        
        # Filter URLs based on selected websites
        urls_to_search = [url for site, url in search_urls.items() if site in selected_websites]
        
        print(f"Selected Bangladeshi websites: {selected_websites}")
        print(f"URLs to search: {urls_to_search}")
        
        if not urls_to_search:
            return {"error": "কোনো ওয়েবসাইট নির্বাচন করা হয়নি। অন্তত একটি বাংলাদেশী প্রপার্টি ওয়েবসাইট নির্বাচন করুন (Bikroy, Bproperty, AmarBari, Bdproperty)"}
        
        # Create comprehensive prompt with Bangladeshi property specifics
        prompt = f"""আপনি বাংলাদেশী রিয়েল এস্টেট ওয়েবসাইট থেকে প্রপার্টি তথ্য বের করছেন। পৃষ্ঠায় যতগুলো প্রপার্টি লিস্টিং আছে সবগুলো বের করুন।

ব্যবহারকারীর অনুসন্ধান মানদণ্ড:
- বাজেট: {user_criteria.get('budget_range', 'যেকোনো')}
- প্রপার্টির ধরণ: {user_criteria.get('property_type', 'যেকোনো')}
- বেডরুম: {user_criteria.get('bedrooms', 'যেকোনো')}
- বাথরুম: {user_criteria.get('bathrooms', 'যেকোনো')}
- ক্ষেত্রফল: {user_criteria.get('min_area', 'যেকোনো')}
- বিশেষ বৈশিষ্ট্য: {user_criteria.get('special_features', 'যেকোনো')}

তথ্য বের করার নির্দেশাবলী:
1. পৃষ্ঠায় সমস্ত প্রপার্টি লিস্টিং খুঁজুন (সাধারণত প্রতি পৃষ্ঠায় ১৫-২৫টি)
2. প্রতিটি প্রপার্টির জন্য নিম্নলিখিত তথ্য বের করুন:
   - address: সম্পূর্ণ ঠিকানা (অবশ্যই প্রয়োজন)
   - price: দাম (টাকা চিহ্ন সহ, উদাহরণ: '৫০ লক্ষ টাকা')
   - bedrooms: বেডরুম সংখ্যা (উদাহরণ: '৩ বেডরুম')
   - bathrooms: বাথরুম সংখ্যা (উদাহরণ: '২ বাথরুম')
   - area: ক্ষেত্রফল (যদি উল্লেখ থাকে, উদাহরণ: '১২০০ sft' বা '৫ কাঠা')
   - property_type: প্রপার্টির ধরণ (ফ্ল্যাট/বাড়ি/জমি/অফিস ইত্যাদি)
   - location_type: অবস্থানের ধরণ (সিটি কর্পোরেশন/উপজেলা/থানা)
   - description: প্রপার্টির বর্ণনা (যদি উল্লেখ থাকে)
   - listing_url: প্রপার্টির ডিটেইলস লিংক (যদি দেখা যায়)
   - contact_info: বিক্রেতা/এজেন্টের যোগাযোগের তথ্য

3. গুরুত্বপূর্ণ নির্দেশাবলী:
   - পৃষ্ঠায় থাকা সমস্ত প্রপার্টি লিস্টিং বের করুন (অন্তত ১০টি যদি থাকে)
   - কোনো ফিল্ড না পেলেও প্রপার্টি বাদ দেবেন না
   - অনুপস্থিত ফিল্ডের জন্য "উল্লেখ নেই" ব্যবহার করুন
   - ঠিকানা এবং দাম সবসময় পূরণ করতে হবে
   - প্রপার্টি কার্ড, লিস্টিং, অনুসন্ধান ফলাফল খুঁজুন

4. রিটার্ন ফরম্যাট:
   - JSON রিটার্ন করুন যাতে "properties" অ্যারে থাকবে
   - প্রতিটি প্রপার্টি একটি পূর্ণাঙ্গ অবজেক্ট হবে
   - "total_count" সেট করুন বের করা প্রপার্টি সংখ্যা অনুযায়ী
   - "source_website" সেট করুন মূল ওয়েবসাইটের নাম অনুযায়ী (Bikroy/Bproperty/AmarBari/Bdproperty)

প্রতিটি দৃশ্যমান প্রপার্টি লিস্টিং বের করুন - কেবল কয়েকটির জন্য সীমিত করবেন না!
        """
        
        try:
            # Direct Firecrawl call
            print(f"Firecrawl এর সাথে {len(urls_to_search)} টি URL নিয়ে কল করা হচ্ছে")
            raw_response = self.firecrawl.extract(
                urls_to_search,
                prompt=prompt,
                schema=PropertyListing.model_json_schema()
            )
            
            print("Raw Firecrawl Response:", raw_response)
            
            if hasattr(raw_response, 'success') and raw_response.success:
                properties = raw_response.data.get('properties', []) if hasattr(raw_response, 'data') else []
                total_count = raw_response.data.get('total_count', 0) if hasattr(raw_response, 'data') else 0
                print(f"Response data keys: {list(raw_response.data.keys()) if hasattr(raw_response, 'data') else 'No data'}")
            elif isinstance(raw_response, dict) and raw_response.get('success'):
                properties = raw_response['data'].get('properties', [])
                total_count = raw_response['data'].get('total_count', 0)
                print(f"Response data keys: {list(raw_response['data'].keys())}")
            else:
                properties = []
                total_count = 0
                print(f"Response failed or unexpected format: {type(raw_response)}")
            
            print(f"{total_count} টি প্রপার্টি থেকে {len(properties)} টি প্রপার্টি বের করা হয়েছে")
            
            # Debug: Print first property if available
            if properties:
                print(f"প্রথম প্রপার্টির নমুনা: {properties[0]}")
                return {
                    'success': True,
                    'properties': properties,
                    'total_count': len(properties),
                    'source_websites': selected_websites
                }
            else:
                # Enhanced error message with debugging info
                error_msg = f"""কোনো প্রপার্টি বের করা যায়নি, যদিও {total_count} টি লিস্টিং পাওয়া গেছে।
                
                সম্ভাব্য কারণ:
                1. ওয়েবসাইটের কাঠামো পরিবর্তিত হয়েছে - এক্সট্র্যাকশন স্কিমা মিলছে না
                2. ওয়েবসাইট ব্লক করছে বা ইন্টারঅ্যাকশন প্রয়োজন (ক্যাপচা, লগইন)
                3. প্রপার্টি নির্দিষ্ট মানদণ্ডের সাথে মিলছে না
                4. এক্সট্র্যাকশন প্রম্পট ওয়েবসাইটের জন্য পরিমার্জিত দরকার
                
                সমাধানের পরামর্শ:
                - ভিন্ন ওয়েবসাইট চেষ্টা করুন (Bikroy, Bproperty, AmarBari, Bdproperty)
                - অনুসন্ধান মানদণ্ড প্রসারিত করুন (যেকোনো বেডরুম, যেকোনো ধরণ, ইত্যাদি)
                - চেক করুন ওয়েবসাইট কি নির্দিষ্ট ইউজার ইন্টারঅ্যাকশন প্রয়োজন করে
                
                ডিবাগ তথ্য: {total_count} টি লিস্টিং পাওয়া গেছে কিন্তু এক্সট্র্যাকশন খালি অ্যারে রিটার্ন করেছে।"""
                
                return {"error": error_msg}
                
        except Exception as e:
            return {"error": f"Firecrawl এক্সট্র্যাকশন ব্যর্থ হয়েছে: {str(e)}"}

def create_sequential_agents(llm, user_criteria):
    """Create agents for sequential manual execution for Bangladeshi market"""
    
    property_search_agent = Agent(
        name="প্রপার্টি অনুসন্ধান এজেন্ট",
        model=llm,
        instructions="""
        আপনি একজন বাংলাদেশী প্রপার্টি অনুসন্ধান বিশেষজ্ঞ। আপনার কাজ হল প্রপার্টি লিস্টিং খুঁজে বের করা এবং বিশ্লেষণ করা।
        
        কাজের প্রক্রিয়া:
        1. প্রপার্টি অনুসন্ধান:
           - প্রদত্ত Firecrawl ডেটা ব্যবহার করে প্রপার্টি লিস্টিং বের করুন
           - ব্যবহারকারীর মানদণ্ড অনুযায়ী প্রপার্টি খুঁজুন
           - বিস্তারিত প্রপার্টি তথ্য বের করুন
        
        2. প্রপার্টি তথ্য বের করা:
           - ঠিকানা, দাম, বেডরুম, বাথরুম, ক্ষেত্রফল
           - প্রপার্টির ধরণ, বৈশিষ্ট্য, লিস্টিং URL
           - এজেন্ট/বিক্রেতার যোগাযোগের তথ্য
        
        3. গঠনমূলক আউটপুট দেওয়া:
           - প্রপার্টি গুলো সম্পূর্ণ বিবরণ সহ তালিকাভুক্ত করুন
           - সমস্ত লিস্টিং URL অন্তর্ভুক্ত করুন
           - ব্যবহারকারীর মানদণ্ড অনুযায়ী মিলের গুণগত মান অনুযায়ী র্যাঙ্ক দিন
        
        গুরুত্বপূর্ণ: 
        - শুধুমাত্র প্রপার্টি তথ্য খোঁজা ও বের করার উপর ফোকাস করুন
        - বাজার বিশ্লেষণ বা মূল্যায়ন দিবেন না
        - আপনার আউটপুট অন্য এজেন্টগুলো দ্বারা বিশ্লেষণের জন্য ব্যবহৃত হবে
        """,
    )
    
    market_analysis_agent = Agent(
        name="বাজার বিশ্লেষণ এজেন্ট",
        model=llm,
        instructions="""
        আপনি একজন বাংলাদেশী রিয়েল এস্টেট বাজার বিশ্লেষণ বিশেষজ্ঞ। সংক্ষিপ্ত ও প্রাসঙ্গিক বাজার অন্তর্দৃষ্টি প্রদান করুন।
        
        প্রয়োজনীয়তা:
        - বিশ্লেষণ সংক্ষিপ্ত ও স্পষ্ট রাখুন
        - মূল বাজার প্রবণতা নিয়ে ফোকাস করুন
        - প্রতিটি ক্ষেত্রে ২-৩ বুলেট পয়েন্ট দিন
        - পুনরাবৃত্তি এড়িয়ে চলুন এবং দীর্ঘ ব্যাখ্যা দিবেন না
        
        আবর্তন করুন:
        1. বাজার অবস্থা: ক্রেতার/বিক্রেতার বাজার, দামের প্রবণতা
        2. প্রধান এলাকা: যে এলাকায় প্রপার্টি গুলো অবস্থিত তার সংক্ষিপ্ত ওভারভিউ
        3. বিনিয়োগ সম্ভাবনা: বাজার বিশ্লেষণের ২-৩ মূল পয়েন্ট
        
        ফরম্যাট: বুলেট পয়েন্ট ব্যবহার করুন এবং প্রতিটি অংশ ১০০ শব্দের মধ্যে রাখুন।
        """,
    )
    
    property_valuation_agent = Agent(
        name="প্রপার্টি মূল্যায়ন এজেন্ট",
        model=llm,
        instructions="""
        আপনি একজন প্রপার্টি মূল্যায়ন বিশেষজ্ঞ। সংক্ষিপ্ত প্রপার্টি মূল্যায়ন প্রদান করুন।
        
        প্রয়োজনীয়তা:
        - প্রতিটি প্রপার্টির মূল্যায়ন ২-৩ বাক্যের মধ্যে রাখুন
        - মূল পয়েন্টের উপর ফোকাস করুন: মূল্য, বিনিয়োগ সম্ভাবনা, সুপারিশ
        - দীর্ঘ বিশ্লেষণ ও পুনরাবৃত্তি এড়িয়ে চলুন
        - বুলেট পয়েন্ট ব্যবহার করুন স্পষ্টতার জন্য
        
        প্রতিটি প্রপার্টির জন্য প্রদান করুন:
        1. মূল্য মূল্যায়ন: ন্যায্য দাম, বেশি/কম দাম
        2. বিনিয়োগ সম্ভাবনা: উচ্চ/মাঝারি/নিম্ন সাথে সংক্ষিপ্ত কারণ
        3. মূল সুপারিশ: একটি কর্মসূচক অন্তর্দৃষ্টি
        
        ফরম্যাট: 
        - বুলেট পয়েন্ট ব্যবহার করুন
        - প্রতিটি প্রপার্টি ৫০ শব্দের মধ্যে রাখুন
        - কর্মসূচক অন্তর্দৃষ্টির উপর ফোকাস করুন
        """,
    )
    
    return property_search_agent, market_analysis_agent, property_valuation_agent

def run_sequential_analysis(city, area, user_criteria, selected_websites, firecrawl_api_key, google_api_key, update_callback):
    """Run agents sequentially with manual coordination for Bangladeshi market"""
    
    # Initialize agents
    llm = Gemini(id="gemini-2.5-flash", api_key=google_api_key)
    property_search_agent, market_analysis_agent, property_valuation_agent = create_sequential_agents(llm, user_criteria)
    
    # Step 1: Property Search with Direct Firecrawl Integration
    update_callback(0.2, "প্রপার্টি অনুসন্ধান চলছে...", "🔍 প্রপার্টি অনুসন্ধান এজেন্ট: প্রপার্টি খুঁজছে...")
    
    direct_agent = BangladeshiPropertyAgent(
        firecrawl_api_key=firecrawl_api_key,
        google_api_key=google_api_key,
        model_id="gemini-2.5-flash"
    )
    
    properties_data = direct_agent.find_properties_direct(
        city=city,
        area=area,
        user_criteria=user_criteria,
        selected_websites=selected_websites
    )
    
    if "error" in properties_data:
        return f"প্রপার্টি অনুসন্ধানে ত্রুটি: {properties_data['error']}"
    
    properties = properties_data.get('properties', [])
    if not properties:
        return "আপনার মানদণ্ড অনুযায়ী কোনো প্রপার্টি পাওয়া যায়নি।"
    
    update_callback(0.4, "প্রপার্টি পাওয়া গেছে", f"✅ {len(properties)} টি প্রপার্টি পাওয়া গেছে")
    
    # Step 2: Market Analysis
    update_callback(0.5, "বাজার বিশ্লেষণ চলছে...", "📊 বাজার বিশ্লেষণ এজেন্ট: বাজার প্রবণতা বিশ্লেষণ করছে...")
    
    market_analysis_prompt = f"""
    এই প্রপার্টি গুলোর জন্য সংক্ষিপ্ত বাজার বিশ্লেষণ প্রদান করুন:
    
    প্রপার্টি: {len(properties)} টি প্রপার্টি {city}, {area} এ
    বাজেট: {user_criteria.get('budget_range', 'যেকোনো')}
    
    নিম্নলিখিত বিষয়ে সংক্ষিপ্ত অন্তর্দৃষ্টি দিন:
    • বাজার অবস্থা (ক্রেতার/বিক্রেতার বাজার)
    • যে এলাকায় প্রপার্টি গুলো অবস্থিত তার সংক্ষিপ্ত ওভারভিউ
    • বিনিয়োগ সম্ভাবনা (সর্বোচ্চ ৩টি বুলেট পয়েন্ট)
    
    প্রতিটি অংশ ১০০ শব্দের মধ্যে রাখুন। বুলেট পয়েন্ট ব্যবহার করুন।
    """
    
    market_result = market_analysis_agent.run(market_analysis_prompt)
    market_analysis = market_result.content
    
    update_callback(0.7, "বাজার বিশ্লেষণ সম্পন্ন", "✅ বাজার বিশ্লেষণ সম্পন্ন হয়েছে")
    
    # Step 3: Property Valuation
    update_callback(0.8, "প্রপার্টি মূল্যায়ন চলছে...", "💰 প্রপার্টি মূল্যায়ন এজেন্ট: প্রপার্টি মূল্যায়ন করছে...")
    
    # Create detailed property list for valuation
    properties_for_valuation = []
    for i, prop in enumerate(properties, 1):
        if isinstance(prop, dict):
            prop_data = {
                'number': i,
                'address': prop.get('address', 'ঠিকানা উল্লেখ নেই'),
                'price': prop.get('price', 'দাম উল্লেখ নেই'),
                'property_type': prop.get('property_type', 'ধরণ উল্লেখ নেই'),
                'bedrooms': prop.get('bedrooms', 'উল্লেখ নেই'),
                'bathrooms': prop.get('bathrooms', 'উল্লেখ নেই'),
                'area': prop.get('area', 'উল্লেখ নেই')
            }
        else:
            prop_data = {
                'number': i,
                'address': getattr(prop, 'address', 'ঠিকানা উল্লেখ নেই'),
                'price': getattr(prop, 'price', 'দাম উল্লেখ নেই'),
                'property_type': getattr(prop, 'property_type', 'ধরণ উল্লেখ নেই'),
                'bedrooms': getattr(prop, 'bedrooms', 'উল্লেখ নেই'),
                'bathrooms': getattr(prop, 'bathrooms', 'উল্লেখ নেই'),
                'area': getattr(prop, 'area', 'উল্লেখ নেই')
            }
        properties_for_valuation.append(prop_data)
    
    valuation_prompt = f"""
    প্রতিটি প্রপার্টির জন্য সংক্ষিপ্ত মূল্যায়ন প্রদান করুন। নিচের নির্দিষ্ট ফরম্যাট অনুসরণ করুন:
    
    ব্যবহারকারীর বাজেট: {user_criteria.get('budget_range', 'যেকোনো')}
    
    মূল্যায়নের জন্য প্রপার্টি:
    {json.dumps(properties_for_valuation, indent=2, ensure_ascii=False)}
    
    প্রতিটি প্রপার্টির জন্য নিচের ফরম্যাটে মূল্যায়ন দিন:
    
    **প্রপার্টি [NUMBER]: [ADDRESS]**
    • মূল্য: [ন্যায্য দাম/বেশি দাম/কম দাম] - [সংক্ষিপ্ত কারণ]
    • বিনিয়োগ সম্ভাবনা: [উচ্চ/মাঝারি/নিম্ন] - [সংক্ষিপ্ত কারণ]
    • সুপারিশ: [একটি কর্মসূচক অন্তর্দৃষ্টি]
    
    প্রয়োজনীয়তা:
    - প্রতিটি মূল্যায়ন **প্রপার্টি [NUMBER]:** দিয়ে শুরু করুন
    - প্রতিটি প্রপার্টির মূল্যায়ন ৫০ শব্দের মধ্যে রাখুন
    - সমস্ত {len(properties)} টি প্রপার্টি আলাদাভাবে বিশ্লেষণ করুন
    - উল্লিখিত ফরম্যাট অনুযায়ী বুলেট পয়েন্ট ব্যবহার করুন
    """
    
    valuation_result = property_valuation_agent.run(valuation_prompt)
    property_valuations = valuation_result.content
    
    update_callback(0.9, "মূল্যায়ন সম্পন্ন", "✅ প্রপার্টি মূল্যায়ন সম্পন্ন হয়েছে")
    
    # Step 4: Final Synthesis
    update_callback(0.95, "ফলাফল সংশ্লেষণ করা হচ্ছে...", "🤖 চূড়ান্ত সুপারিশ তৈরি করা হচ্ছে...")
    
    # Format properties for better display
    properties_display = ""
    for i, prop in enumerate(properties, 1):
        # Handle both dict and object access
        if isinstance(prop, dict):
            address = prop.get('address', 'ঠিকানা উল্লেখ নেই')
            price = prop.get('price', 'দাম উল্লেখ নেই')
            prop_type = prop.get('property_type', 'ধরণ উল্লেখ নেই')
            bedrooms = prop.get('bedrooms', 'উল্লেখ নেই')
            bathrooms = prop.get('bathrooms', 'উল্লেখ নেই')
            area = prop.get('area', 'উল্লেখ নেই')
            contact_info = prop.get('contact_info', 'যোগাযোগের তথ্য উল্লেখ নেই')
            description = prop.get('description', 'বর্ণনা উল্লেখ নেই')
            listing_url = prop.get('listing_url', '#')
        else:
            address = getattr(prop, 'address', 'ঠিকানা উল্লেখ নেই')
            price = getattr(prop, 'price', 'দাম উল্লেখ নেই')
            prop_type = getattr(prop, 'property_type', 'ধরণ উল্লেখ নেই')
            bedrooms = getattr(prop, 'bedrooms', 'উল্লেখ নেই')
            bathrooms = getattr(prop, 'bathrooms', 'উল্লেখ নেই')
            area = getattr(prop, 'area', 'উল্লেখ নেই')
            contact_info = getattr(prop, 'contact_info', 'যোগাযোগের তথ্য উল্লেখ নেই')
            description = getattr(prop, 'description', 'বর্ণনা উল্লেখ নেই')
            listing_url = getattr(prop, 'listing_url', '#')
        
        properties_display += f"""
### প্রপার্টি {i}: {address}

**দাম:** {price}  
**ধরণ:** {prop_type}  
**বেডরুম:** {bedrooms} | **বাথরুম:** {bathrooms}  
**ক্ষেত্রফল:** {area}  
**যোগাযোগ:** {contact_info}  

**বর্ণনা:** {description}  

**লিস্টিং URL:** [প্রপার্টি দেখুন]({listing_url})  

---
"""
    
    final_synthesis = f"""
# 🏠 প্রপার্টি লিস্টিং পাওয়া গেছে

**মোট প্রপার্টি:** {len(properties)} টি আপনার মানদণ্ড অনুযায়ী

{properties_display}

---

# 📊 বাজার বিশ্লেষণ ও বিনিয়োগ অন্তর্দৃষ্টি

        {market_analysis}

---
    
# 💰 প্রপার্টি মূল্যায়ন ও সুপারিশ
    
        {property_valuations}

---

# 🔗 সমস্ত প্রপার্টি লিঙ্ক
    """
    
    # Extract and add property links
    all_text = f"{json.dumps(properties, indent=2, ensure_ascii=False)} {market_analysis} {property_valuations}"
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', all_text)
    
    if urls:
        final_synthesis += "\n### প্রাপ্য প্রপার্টি লিঙ্ক:\n"
        for i, url in enumerate(set(urls), 1):
            final_synthesis += f"{i}. {url}\n"
    
    update_callback(1.0, "বিশ্লেষণ সম্পন্ন", "🎉 সম্পূর্ণ বিশ্লেষণ প্রস্তুত!")
    
    # Return structured data for better UI display
    return {
        'properties': properties,
        'market_analysis': market_analysis,
        'property_valuations': property_valuations,
        'markdown_synthesis': final_synthesis,
        'total_properties': len(properties)
    }

def extract_property_valuation(property_valuations, property_number, property_address):
    """Extract valuation for a specific property from the full analysis"""
    if not property_valuations:
        return None
    
    # Split by property sections - look for the formatted property headers
    sections = property_valuations.split('**প্রপার্টি')
    
    # Look for the specific property number
    for section in sections:
        if section.strip().startswith(f"{property_number}:"):
            # Add back the "**প্রপার্টি" prefix and clean up
            clean_section = f"**প্রপার্টি{section}".strip()
            # Remove any extra asterisks at the end
            clean_section = clean_section.replace('**', '**').replace('***', '**')
            return clean_section
    
    # Fallback: look for property number mentions in any format
    all_sections = property_valuations.split('\n\n')
    for section in all_sections:
        if (f"প্রপার্টি {property_number}" in section or 
            f"#{property_number}" in section):
            return section
    
    # Last resort: try to match by address
    for section in all_sections:
        if any(word in section.lower() for word in property_address.lower().split()[:3] if len(word) > 2):
            return section
    
    # If no specific match found, return indication that analysis is not available
    return f"**প্রপার্টি {property_number} বিশ্লেষণ**\n• বিশ্লেষণ: পৃথক মূল্যায়ন পাওয়া যায়নি\n• সুপারিশ: বাজার বিশ্লেষণ ট্যাবে সাধারণ বিশ্লেষণ দেখুন"

def display_properties_professionally(properties, market_analysis, property_valuations, total_properties):
    """Display properties in a clean, professional UI using Streamlit components for Bangladeshi market"""
    
    # Header with key metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("পাওয়া প্রপার্টি", total_properties)
    with col2:
        # Calculate average price
        prices = []
        for p in properties:
            price_str = p.get('price', '') if isinstance(p, dict) else getattr(p, 'price', '')
            if price_str and price_str != 'দাম উল্লেখ নেই':
                try:
                    # Extract numeric value from Bangladeshi price format (e.g., "৫০ লক্ষ টাকা")
                    price_num = ''.join(filter(str.isdigit, str(price_str)))
                    if price_num:
                        prices.append(int(price_num))
                except:
                    pass
        avg_price = f"{sum(prices) // len(prices):,} টাকা" if prices else "উল্লেখ নেই"
        st.metric("গড় দাম", avg_price)
    with col3:
        types = {}
        for p in properties:
            t = p.get('property_type', 'অজানা') if isinstance(p, dict) else getattr(p, 'property_type', 'অজানা')
            types[t] = types.get(t, 0) + 1
        most_common = max(types.items(), key=lambda x: x[1])[0] if types else "উল্লেখ নেই"
        st.metric("সাধারণ ধরণ", most_common)
    
    # Create tabs for different views
    tab1, tab2, tab3 = st.tabs(["🏠 প্রপার্টি", "📊 বাজার বিশ্লেষণ", "💰 মূল্যায়ন"])
    
    with tab1:
        for i, prop in enumerate(properties, 1):
            # Extract property data
            data = {k: prop.get(k, '') if isinstance(prop, dict) else getattr(prop, k, '') 
                   for k in ['address', 'price', 'property_type', 'bedrooms', 'bathrooms', 'area', 'description', 'listing_url', 'contact_info']}
            
            with st.container():
                # Property header with number and price
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(f"#{i} 🏠 {data['address']}")
                with col2:
                    st.metric("দাম", data['price'])
                
                # Property details with right-aligned button
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**ধরণ:** {data['property_type']}")
                    st.markdown(f"**বেড/বাথ:** {data['bedrooms']}/{data['bathrooms']}")
                    st.markdown(f"**ক্ষেত্রফল:** {data['area']}")
                with col2:
                    with st.expander("💰 বিনিয়োগ বিশ্লেষণ"):
                        # Extract property-specific valuation from the full analysis
                        property_valuation = extract_property_valuation(property_valuations, i, data['address'])
                        if property_valuation:
                            st.markdown(property_valuation)
                        else:
                            st.info("এই প্রপার্টির জন্য বিনিয়োগ বিশ্লেষণ পাওয়া যায়নি")
                with col3:
                    if data['listing_url'] and data['listing_url'] != '#':
                        st.markdown(
                            f"""
                            <div style="height: 100%; display: flex; align-items: center; justify-content: flex-end;">
                                <a href="{data['listing_url']}" target="_blank" 
                                   style="text-decoration: none; padding: 0.5rem 1rem; 
                                   background-color: #0066cc; color: white; 
                                   border-radius: 6px; font-size: 0.9em; font-weight: 500;">
                                    প্রপার্টি লিঙ্ক
                                </a>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                
                st.divider()
    
    with tab2:
        st.subheader("📊 বাজার বিশ্লেষণ")
        if market_analysis:
            for section in market_analysis.split('\n\n'):
                if section.strip():
                    st.markdown(section)
        else:
            st.info("কোনো বাজার বিশ্লেষণ পাওয়া যায়নি")
    
    with tab3:
        st.subheader("💰 বিনিয়োগ বিশ্লেষণ")
        if property_valuations:
            for section in property_valuations.split('\n\n'):
                if section.strip():
                    st.markdown(section)
        else:
            st.info("কোনো মূল্যায়ন তথ্য পাওয়া যায়নি")

def main():
    st.set_page_config(
        page_title="AI রিয়েল এস্টেট এজেন্ট টিম (বাংলাদেশ)", 
        page_icon="🏠", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Clean header
    st.title("🏠 AI রিয়েল এস্টেট এজেন্ট টিম (বাংলাদেশ)")
    st.caption("আপনার স্বপ্নের বাড়ি খুঁজুন বিশেষায়িত AI এজেন্টের সাহায্যে")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ কনফিগারেশন")
        
        # API Key inputs with validation
        with st.expander("🔑 API কী", expanded=True):
            google_key = st.text_input(
                "Google AI API কী", 
                value=DEFAULT_GOOGLE_API_KEY, 
                type="password",
                help="https://aistudio.google.com/app/apikey  থেকে আপনার API কী পান",
                placeholder="AIza..."
            )
            firecrawl_key = st.text_input(
                "Firecrawl API কী", 
                value=DEFAULT_FIRECRAWL_API_KEY, 
                type="password",
                help="https://firecrawl.dev  থেকে আপনার API কী পান",
                placeholder="fc_..."
            )
            
            # Update environment variables
            if google_key: os.environ["GOOGLE_API_KEY"] = google_key
            if firecrawl_key: os.environ["FIRECRAWL_API_KEY"] = firecrawl_key
        
        # Website selection
        with st.expander("🌐 অনুসন্ধান উৎস", expanded=True):
            st.markdown("**বাংলাদেশী প্রপার্টি ওয়েবসাইট নির্বাচন করুন:**")
            available_websites = ["Bikroy.com", "Bproperty.com", "AmarBari.com", "Bdproperty.com", "Chaldal Property", "ShareBazar"]
            selected_websites = [site for site in available_websites if st.checkbox(site, value=site in ["Bikroy.com", "Bproperty.com"])]
            
            if selected_websites:
                st.markdown(f'✅ {len(selected_websites)} টি উৎস নির্বাচিত', unsafe_allow_html=True)
            else:
                st.markdown('<div class="status-error">⚠️ অন্তত একটি ওয়েবসাইট নির্বাচন করুন</div>', unsafe_allow_html=True)
        
        # How it works
        with st.expander("🤖 কিভাবে কাজ করে", expanded=False):
            st.markdown("**🔍 প্রপার্টি অনুসন্ধান এজেন্ট**")
            st.markdown("সরাসরি Firecrawl ইন্টিগ্রেশন ব্যবহার করে প্রপার্টি খুঁজে")
            
            st.markdown("**📊 বাজার বিশ্লেষণ এজেন্ট**")
            st.markdown("বাজার প্রবণতা ও এলাকা সম্পর্কিত অন্তর্দৃষ্টি বিশ্লেষণ করে")
            
            st.markdown("**💰 প্রপার্টি মূল্যায়ন এজেন্ট**")
            st.markdown("প্রপার্টি মূল্যায়ন করে এবং বিনিয়োগ বিশ্লেষণ প্রদান করে")
    
    # Main form
    st.header("আপনার প্রপার্টি প্রয়োজনীয়তা")
    st.info("অনুগ্রহ করে অবস্থান, বাজেট এবং প্রপার্টি বিবরণ প্রদান করুন যাতে আমরা আপনার জন্য আদর্শ বাড়ি খুঁজতে পারি।")
    
    with st.form("property_preferences"):
        # Location and Budget Section
        st.markdown("### 📍 অবস্থান & বাজেট")
        col1, col2 = st.columns(2)
        
        with col1:
            city = st.selectbox(
                "🏙️ শহর/জেলা", 
                ["ঢাকা", "চট্টগ্রাম", "খুলনা", "রাজশাহী", "সিলেট", "বরিশাল", "রংপুর", "ময়মনসিংহ"],
                help="আপনি যে শহরে প্রপার্টি খুঁজছেন"
            )
            area = st.text_input(
                "🏘️ এলাকা (ঐচ্ছিক)", 
                placeholder="উদাহরণ: বনানী, গুলশান, মিরপুর",
                help="আপনি যে এলাকায় প্রপার্টি খুঁজছেন"
            )
        
        with col2:
            min_price = st.number_input(
                "💰 ন্যূনতম দাম (টাকা)", 
                min_value=0, 
                value=5000000, 
                step=500000,
                help="আপনার ন্যূনতম বাজেট"
            )
            max_price = st.number_input(
                "💰 সর্বোচ্চ দাম (টাকা)", 
                min_value=0, 
                value=20000000, 
                step=1000000,
                help="আপনার সর্বোচ্চ বাজেট"
            )
        
        # Property Details Section
        st.markdown("### 🏡 প্রপার্টি বিবরণ")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            property_type = st.selectbox(
                "🏠 প্রপার্টির ধরণ",
                ["যেকোনো", "ফ্ল্যাট", "বাড়ি", "জমি", "অফিস", "দোকান"],
                help="আপনি যে ধরণের প্রপার্টি খুঁজছেন"
            )
            bedrooms = st.selectbox(
                "🛏️ বেডরুম",
                ["যেকোনো", "১", "২", "৩", "৪", "৫+"],
                help="প্রয়োজনীয় বেডরুম সংখ্যা"
            )
        
        with col2:
            bathrooms = st.selectbox(
                "🚿 বাথরুম",
                ["যেকোনো", "১", "১.৫", "২", "২.৫", "৩", "৩.৫", "৪+"],
                help="প্রয়োজনীয় বাথরুম সংখ্যা"
            )
            min_area = st.number_input(
                "📏 ন্যূনতম ক্ষেত্রফল (sft)",
                min_value=0,
                value=800,
                step=100,
                help="প্রয়োজনীয় ন্যূনতম ক্ষেত্রফল"
            )
        
        with col3:
            timeline = st.selectbox(
                "⏰ সময়সীমা",
                ["নমনীয়", "১-৩ মাস", "৩-৬ মাস", "৬+ মাস"],
                help="আপনি কতদিনের মধ্যে কিনতে চান?"
            )
            urgency = st.selectbox(
                "🚨 জরুরীতা",
                ["জরুরী নয়", "কিছুটা জরুরী", "অত্যন্ত জরুরী"],
                help="আপনার ক্রয়ের জরুরীতা কত?"
            )
        
        # Special Features
        st.markdown("### ✨ বিশেষ বৈশিষ্ট্য")
        special_features = st.text_area(
            "🎯 বিশেষ বৈশিষ্ট্য ও প্রয়োজনীয়তা",
            placeholder="উদাহরণ: পার্কিং স্থান, বারান্দা, ভালো স্কুলের কাছাকাছি, পাবলিক ট্রান্সপোর্টের কাছাকাছি, ইত্যাদি",
            help="আপনার জন্য গুরুত্বপূর্ণ কোনো বিশেষ বৈশিষ্ট্য আছে?"
        )
        
        # Submit button with custom styling
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button(
                "🚀 প্রপার্টি বিশ্লেষণ শুরু করুন",
                type="primary",
                use_container_width=True
            )
    
    # Process form submission
    if submitted:
        # Validate all required inputs
        missing_items = []
        if not google_key:
            missing_items.append("Google AI API কী")
        if not firecrawl_key:
            missing_items.append("Firecrawl API কী")
        if not city:
            missing_items.append("শহর/জেলা")
        if not selected_websites:
            missing_items.append("অন্তত একটি ওয়েবসাইট নির্বাচন")
        
        if missing_items:
            st.markdown(f"""
            <div class="status-error" style="text-align: center; margin: 2rem 0;">
                ⚠️ অনুগ্রহ করে প্রদান করুন: {', '.join(missing_items)}
            </div>
            """, unsafe_allow_html=True)
            return
        
        try:
            user_criteria = {
                'budget_range': f"{min_price:,} - {max_price:,} টাকা",
                'property_type': property_type,
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'min_area': min_area,
                'special_features': special_features if special_features else 'কোনো বিশেষ বৈশিষ্ট্য উল্লেখ নেই'
            }
            
        except Exception as e:
            st.markdown(f"""
            <div class="status-error" style="text-align: center; margin: 2rem 0;">
                ❌ ত্রুটি: {str(e)}
            </div>
            """, unsafe_allow_html=True)
            return
        
        # Display progress
        st.markdown("#### প্রপার্টি বিশ্লেষণ চলছে")
        st.info("AI এজেন্ট গুলো আপনার জন্য আদর্শ বাড়ি খুঁজছে...")
        
        status_container = st.container()
        with status_container:
            st.markdown("### 📊 বর্তমান কার্যক্রম")
            progress_bar = st.progress(0)
            current_activity = st.empty()
        
        def update_progress(progress, status, activity=None):
            if activity:
                progress_bar.progress(progress)
                current_activity.text(activity)
        
        try:
            start_time = time.time()
            update_progress(0.1, "শুরু হচ্ছে...", "ধারাবাহিক প্রপার্টি বিশ্লেষণ শুরু হচ্ছে")
            
            # Run sequential analysis with manual coordination
            final_result = run_sequential_analysis(
                city=city,
                area=area,
                user_criteria=user_criteria,
                selected_websites=selected_websites,
                firecrawl_api_key=firecrawl_key,
                google_api_key=google_key,
                update_callback=update_progress
            )
            
            total_time = time.time() - start_time
            
            # Display results
            if isinstance(final_result, dict):
                # Use the new professional display
                display_properties_professionally(
                    final_result['properties'],
                    final_result['market_analysis'],
                    final_result['property_valuations'],
                    final_result['total_properties']
                )
            else:
                # Fallback to markdown display
                st.markdown("### 🏠 সম্পূর্ণ রিয়েল এস্টেট বিশ্লেষণ")
                st.markdown(final_result)
            
            # Timing info in a subtle way
            st.caption(f"বিশ্লেষণ {total_time:.1f} সেকেন্ডে সম্পন্ন হয়েছে")
            
        except Exception as e:
            st.markdown(f"""
            <div class="status-error" style="text-align: center; margin: 2rem 0;">
                ❌ ত্রুটি ঘটেছে: {str(e)}
            </div>
            """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()