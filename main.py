import os
from crewai import Agent, Task, Crew, LLM
from langchain.tools import Tool
from SearchTool import SearchTools
from datetime import datetime
from linkedin_poster import LinkedInPoster
from pydantic.v1 import BaseModel, Field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

print(f"API Key present: {'GOOGLE_API_KEY' in os.environ}")

# Initialize LLM
my_llm = LLM(
    api_key=os.getenv("GOOGLE_API_KEY"),
    model="gemini/gemini-pro",
    temperature=0.7
)

# Initialize tools
search_tools = SearchTools()

# News Researcher Agent
news_researcher = Agent(
    role='Tech News Researcher',
    goal='Find the most viral and impactful tech news story of today',
    backstory="""You are an expert tech journalist who can identify the most significant 
    and viral tech story that professionals need to know about.""",
    verbose=True,
    allow_delegation=False,
    tools=[
        Tool(
            name="search_internet",
            func=lambda x: search_tools.search_internet(x),
            description="Search for trending tech news. Input should be a search query string."
        ),
        Tool(
            name="medium_article_summary",
            func=search_tools.medium_article_summary,
            description="Get detailed content from a Medium article. Input should be a URL string."
        ),
        Tool(
            name="search_instagram",
            func=search_tools.search_instagram,
            description="Search for Instagram posts about a topic. Input should be a search query string."
        ),
        Tool(
            name="generate_image",
            func=search_tools.generate_image,
            description="Generate an image using the Inference API based on the provided prompt. Input should be a prompt string and a save path."
        )
    ],
    llm=my_llm
)

# Content Analyzer Agent
content_analyzer = Agent(
    role='Content Analyzer',
    goal='Provide deep analysis of the tech news story',
    backstory="""You are a leading tech industry analyst who excels at identifying 
    business implications and future trends. You provide strategic insights that 
    professionals need to know.""",
    verbose=True,
    allow_delegation=True,
    llm=my_llm,
    tools=[
        Tool(
            name="medium_article_summary",
            func=search_tools.medium_article_summary,
            description="Analyze article content. Input should be a URL string."
        )
    ]
)

# LinkedIn Post Creator
linkedin_creator = Agent(
    role='LinkedIn Content Strategist',
    goal='Create a viral, engaging LinkedIn post',
    backstory="""You are an expert at creating viral LinkedIn content with high engagement. 
    You know exactly how to structure posts, use emojis strategically, and craft hooks 
    that capture attention. Your posts always provide value and generate discussion.""",
    verbose=True,
    allow_delegation=True,
    llm=my_llm,
    tools=[
        Tool(
            name="search_internet",
            func=lambda x: search_tools.search_internet(x),
            description="Research trending topics and hashtags. Input should be a search query string."
        ),
        Tool(
            name="generate_image",
            func=search_tools.generate_image,
            description="Generate an image based on a prompt. Input should be a prompt string and a save path."
        )
    ]
)

# Define tasks
task1 = Task(
    description="""Find today's most viral and impactful tech news story.
    
    1. Search for and identify the SINGLE most significant tech story that:
       - Is groundbreaking or industry-changing
       - Has major implications for professionals
       - Is highly discussable and engaging
       - Is from a credible source
       - Is very recent (within last 24 hours)
    
    2. Format the story exactly as follows:
    
    ---STORY START---
    Title: [Story Title]
    Source: [Source Name]
    URL: [URL]
    Date: [Publication Date]
    
    Summary:
    [2-3 paragraphs summarizing the key points]
    
    Key Statistics:
    • [Stat 1]
    • [Stat 2]
    • [Stat 3]
    
    Industry Impact:
    [2-3 paragraphs on implications]
    ---STORY END---""",
    expected_output="Expected output format for the news story",
    agent=news_researcher
)

task2 = Task(
    description="""Analyze the news story for professional insights.
    
    ---ANALYSIS START---
    Business Impact:
    • Short-term: [Immediate effects]
    • Long-term: [Future implications]
    • Market opportunities: [List 2-3]
    • Potential risks: [List 2-3]
    
    Stakeholder Analysis:
    • Winners: [Who benefits and why]
    • Challenges: [Who faces disruption]
    • Action items: [What professionals should do]
    
    Strategic Insights:
    • Industry trends: [Key trends]
    • Career implications: [Impact on jobs/skills]
    • Recommendations: [Strategic advice]
    ---ANALYSIS END---""",
    expected_output="Expected output format for the analysis",
    agent=content_analyzer
)

task3 = Task(
    description="""Create one viral LinkedIn post that will drive maximum engagement.
    
    Your output MUST start with '---POST START---' and end with '---POST END---' exactly.
    
    Create a post with this structure:
    
    ---POST START---
    🔥 [Attention-Grabbing Headline] 🚀 💡
    
    [Compelling 2-3 line hook that creates curiosity]
    
    Breaking News: [One-line news summary]
    
    Why This Matters:
    • [Key Point 1]
    • [Key Point 2]
    • [Key Point 3]
    
    Industry Impact:
    [2-3 lines on implications for professionals]
    
    My Take:
    [Unique perspective + controversial/debatable point]
    
    The Big Question:
    [Thought-provoking question that encourages comments]
    
    Call to Action:
    [Clear ask for engagement/discussion]
    
    #AI #Technology #Innovation #FutureOfWork #TechNews
    ---POST END---
    
    Requirements:
    - Must include the exact markers as shown above
    - Exactly 3 emojis in headline
    - 1300-1700 characters
    - Must include all sections
    - Must be highly engaging
    - Must encourage discussion""",
    expected_output="Expected output format for the LinkedIn post",
    agent=linkedin_creator
)

# Create the crew
crew = Crew(
    agents=[news_researcher, content_analyzer, linkedin_creator],
    tasks=[task1, task2, task3],
    verbose=True
)

# Create posts directory if it doesn't exist
posts_dir = "linkedin_posts"
if not os.path.exists(posts_dir):
    os.makedirs(posts_dir)

# Run the crew
result = crew.kickoff()

# Save results
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

try:
    # Create a directory for this run
    run_dir = os.path.join(posts_dir, timestamp)
    os.makedirs(run_dir)
    
    # Convert CrewOutput to string
    result_str = str(result)
    
    # Save full output
    with open(os.path.join(run_dir, 'full_output.txt'), 'w', encoding='utf-8') as f:
        f.write(result_str)
    
    # Save individual components
    for content_type in ['STORY', 'ANALYSIS', 'POST']:
        start_marker = f"---{content_type} START---"
        end_marker = f"---{content_type} END---"
        
        try:
            if start_marker in result_str and end_marker in result_str:
                content = result_str.split(start_marker)[1].split(end_marker)[0].strip()
                filename = f"{content_type.lower()}.txt"
                with open(os.path.join(run_dir, filename), 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                print(f"Warning: Could not find {content_type}")
        except Exception as e:
            print(f"Error saving {content_type}: {str(e)}")
    
    print(f"\nContent saved in: {run_dir}")
    
    # Automatically post to LinkedIn
    print("\nAttempting to post to LinkedIn...")
    try:
        linkedin_poster = LinkedInPoster()
        success = linkedin_poster.post_to_linkedin()
        if success:
            print("Successfully posted to LinkedIn!")
        else:
            print("Failed to post to LinkedIn. Check the error messages above.")
    except Exception as e:
        print(f"Error during LinkedIn posting: {str(e)}")
    
except Exception as e:
    print(f"Error saving content: {str(e)}")
    # Fallback: save to output.txt in current directory
    with open('output.txt', 'w', encoding='utf-8') as f:
        f.write(str(result))

# Print the result
print("\n######################\n")
print(result)