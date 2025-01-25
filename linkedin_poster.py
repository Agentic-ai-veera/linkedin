import os
import json
import time
import pickle
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class LinkedInPoster:
    def __init__(self):
        load_dotenv()
        
        # Initialize Chrome options
        self.options = Options()
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-notifications')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.options.add_experimental_option('useAutomationExtension', False)
        
        # Path for cookies file
        self.cookies_file = 'linkedin_cookies.pkl'
        
        # LinkedIn credentials (only needed for first login)
        self.email = os.getenv('LINKEDIN_EMAIL')
        self.password = os.getenv('LINKEDIN_PASSWORD')

    def get_driver(self):
        """Get Chrome driver with proper version"""
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=self.options)
        
        # Add stealth script
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        # Add headless option
        self.options.add_argument('--headless')
        
        return driver

    def save_cookies(self, driver):
        """Save cookies to file"""
        try:
            # Wait a bit to ensure all cookies are set
            time.sleep(3)
            cookies = driver.get_cookies()
            
            # Only save if we have essential cookies
            essential_cookies = ['li_at', 'JSESSIONID']
            if any(cookie['name'] in essential_cookies for cookie in cookies):
                with open(self.cookies_file, 'wb') as f:
                    pickle.dump(cookies, f)
                print("Cookies saved successfully!")
                return True
            else:
                print("Warning: Essential cookies not found")
                return False
        except Exception as e:
            print(f"Error saving cookies: {str(e)}")
            return False

    def load_cookies(self, driver):
        """Load cookies from file"""
        try:
            if not os.path.exists(self.cookies_file):
                print("No cookies file found")
                return False
            
            with open(self.cookies_file, 'rb') as f:
                cookies = pickle.load(f)
            
            # Check cookie expiration
            current_time = datetime.now().timestamp()
            valid_cookies = []
            
            for cookie in cookies:
                # Skip expired cookies
                if 'expiry' in cookie and cookie['expiry'] <= current_time:
                    continue
                # Remove problematic attributes
                for k in ['expiry', 'expires', 'domain']:
                    cookie.pop(k, None)
                valid_cookies.append(cookie)
            
            if not valid_cookies:
                print("No valid cookies found")
                return False
            
            # Add cookies to driver
            for cookie in valid_cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"Warning: Could not add cookie {cookie.get('name')}: {str(e)}")
                
            print("Cookies loaded successfully!")
            return True
            
        except Exception as e:
            print(f"Error loading cookies: {str(e)}")
            return False

    def check_login_status(self, driver):
        """Check if we're logged in"""
        try:
            driver.get('https://www.linkedin.com/feed/')
            time.sleep(5)
            
            # Check URL first
            if not driver.current_url.startswith('https://www.linkedin.com/feed'):
                print("Not on feed page after navigation")
                return False
            
            # Try multiple selectors to verify login
            login_indicators = [
                'share-box-feed-entry__trigger',
                'global-nav__me-trigger',
                'feed-identity-module',
                'global-nav__primary-link'
            ]
            
            for selector in login_indicators:
                try:
                    element = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, selector))
                    )
                    if element.is_displayed():
                        print(f"Login verified with selector: {selector}")
                        return True
                except:
                    continue
                
            print("Could not verify login status")
            return False
        except Exception as e:
            print(f"Error checking login status: {str(e)}")
            return False

    def login_to_linkedin(self, driver):
        """Login to LinkedIn"""
        try:
            # First try to load saved cookies
            driver.get('https://www.linkedin.com')
            time.sleep(5)
            
            if os.path.exists(self.cookies_file):
                print("Found existing cookies, attempting to use them...")
                if self.load_cookies(driver):
                    driver.refresh()
                    time.sleep(5)
                    
                    # Check if we're logged in
                    if self.check_login_status(driver):
                        print("Successfully logged in using saved cookies!")
                        return True
                    else:
                        print("Cookie login failed, removing cookie file")
                        os.remove(self.cookies_file)
            
            # If we get here, we need to do manual login
            if not self.email or not self.password:
                raise ValueError("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env file for login")
            
            print("Performing manual login...")
            driver.get('https://www.linkedin.com/login')
            time.sleep(5)
            
            # Enter credentials and login
            try:
                email_field = driver.find_element(By.ID, 'username')
                email_field.clear()
                time.sleep(1)
                email_field.send_keys(self.email)
                time.sleep(2)
                
                password_field = driver.find_element(By.ID, 'password')
                password_field.clear()
                time.sleep(1)
                password_field.send_keys(self.password)
                time.sleep(2)
                
                password_field.send_keys(Keys.RETURN)
                time.sleep(10)
                
                # Verify login and save cookies
                if self.check_login_status(driver):
                    print("Manual login successful!")
                    if self.save_cookies(driver):
                        print("New login cookies saved")
                    return True
                else:
                    print("Login verification failed")
                    return False
                
            except Exception as e:
                print(f"Error during manual login: {str(e)}")
                return False
            
        except Exception as e:
            print(f"Login process failed: {str(e)}")
            if driver.current_url != "https://www.linkedin.com/login":
                print(f"Current URL: {driver.current_url}")
            return False

    def create_post(self, driver, content):
        """Create a new post"""
        try:
            # Go to feed page and wait
            driver.get('https://www.linkedin.com/feed/')
            time.sleep(5)
            
            # Try to find and click the post button using different approaches
            post_button_found = False
            
            # Approach 1: Direct CSS selector
            try:
                post_button = driver.find_element(By.CSS_SELECTOR, "button[data-control-name='share.sharebox_focus']")
                driver.execute_script("arguments[0].click();", post_button)
                post_button_found = True
            except:
                print("Approach 1 failed")
            
            # Approach 2: Find by partial text
            if not post_button_found:
                try:
                    post_button = driver.find_element(By.XPATH, "//button[contains(.,'Start a post')]")
                    driver.execute_script("arguments[0].click();", post_button)
                    post_button_found = True
                except:
                    print("Approach 2 failed")
            
            # Approach 3: Find by complex XPath
            if not post_button_found:
                try:
                    post_button = driver.find_element(By.XPATH, "//div[contains(@class, 'share-box-feed-entry__trigger')]")
                    driver.execute_script("arguments[0].click();", post_button)
                    post_button_found = True
                except:
                    print("Approach 3 failed")
                
            if not post_button_found:
                # Take screenshot before failing
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                driver.save_screenshot(f"pre_post_error_{timestamp}.png")
                raise Exception("Could not find post button")
            
            time.sleep(5)
            
            # Find post input field using multiple approaches
            post_field = None
            
            # Approach 1: Wait for editor
            try:
                post_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-placeholder='What do you want to talk about?']"))
                )
            except:
                print("Editor approach 1 failed")
            
            # Approach 2: Try alternate selector
            if not post_field:
                try:
                    post_field = driver.find_element(By.CSS_SELECTOR, "div.ql-editor")
                except:
                    print("Editor approach 2 failed")
            
            # Approach 3: Try XPath
            if not post_field:
                try:
                    post_field = driver.find_element(By.XPATH, "//div[contains(@class, 'editor-content')]")
                except:
                    print("Editor approach 3 failed")
            
            if not post_field:
                raise Exception("Could not find post input field")
            
            # Clear existing content and wait
            driver.execute_script("arguments[0].innerHTML = '';", post_field)
            time.sleep(2)
            
            # Split content into paragraphs
            paragraphs = content.split('\n\n')
            
            # Enter content paragraph by paragraph
            for paragraph in paragraphs:
                if paragraph.strip():
                    # Use JavaScript to insert HTML content
                    html_content = paragraph.replace('\n', '<br>')
                    driver.execute_script(
                        "arguments[0].innerHTML += arguments[1] + '<br><br>';",
                        post_field,
                        html_content
                    )
                    time.sleep(0.5)
            
            time.sleep(3)
            
            # Find and click the Post button using multiple approaches
            post_button = None
            
            # Approach 1: Primary button
            try:
                post_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.share-actions__primary-action"))
                )
            except:
                print("Post button approach 1 failed")
            
            # Approach 2: Text content
            if not post_button:
                try:
                    post_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Post')]")
                except:
                    print("Post button approach 2 failed")
            
            # Approach 3: Complex selector
            if not post_button:
                try:
                    post_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                except:
                    print("Post button approach 3 failed")
            
            if not post_button:
                raise Exception("Could not find post button")
            
            # Click the post button using JavaScript
            driver.execute_script("arguments[0].click();", post_button)
            
            # Wait for post to be published
            time.sleep(10)
            
            # Verify post was successful by checking for success indicators
            success_indicators = [
                "//div[contains(@class, 'share-box-feed-entry__trigger')]",  # Feed entry visible
                "//div[contains(@class, 'feed-shared-update-v2')]",  # New post in feed
                "//span[contains(text(), 'Post successful')]"  # Success message
            ]
            
            for indicator in success_indicators:
                try:
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, indicator))
                    )
                    if element.is_displayed():
                        print(f"Post verified with indicator: {indicator}")
                        return True
                except:
                    continue
            
            # If we got here, we couldn't verify but the post might still have worked
            print("Warning: Could not verify post success, but no errors detected")
            return True
            
        except Exception as e:
            print(f"Error creating post: {str(e)}")
            print(f"Current URL: {driver.current_url}")
            # Take screenshot for debugging
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                driver.save_screenshot(f"error_screenshot_{timestamp}.png")
                print(f"Error screenshot saved as error_screenshot_{timestamp}.png")
                
                # Print page source for debugging
                print("Page source preview:")
                print(driver.page_source[:1000])
            except:
                pass
            return False

    def post_to_linkedin(self, content=None):
        """Post content to LinkedIn"""
        driver = None
        try:
            # Get content if not provided
            if content is None:
                content = self.get_latest_post()
            
            # Format the post
            formatted_content = self.format_post(content)
            
            # Initialize Chrome driver
            driver = self.get_driver()
            driver.maximize_window()
            
            # Login to LinkedIn
            if not self.login_to_linkedin(driver):
                raise Exception("Failed to login to LinkedIn")
            
            # Create the post
            if not self.create_post(driver, formatted_content):
                raise Exception("Failed to create post")
            
            # Log the successful post
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_dir = "linkedin_logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            log_file = os.path.join(log_dir, f"post_log_{timestamp}.txt")
            with open(log_file, 'w') as f:
                f.write(f"Posted at: {timestamp}\n")
                f.write(f"Content:\n{formatted_content}\n")
                
            print(f"Successfully posted to LinkedIn! Log saved to {log_file}")
            return True
            
        except Exception as e:
            print(f"Error posting to LinkedIn: {str(e)}")
            return False
            
        finally:
            if driver:
                driver.quit()

    def get_latest_post(self):
        """Get the most recently generated post"""
        posts_dir = "linkedin_posts"
        if not os.path.exists(posts_dir):
            raise Exception("No posts directory found")
            
        # Get the most recent directory
        directories = [d for d in os.listdir(posts_dir) if os.path.isdir(os.path.join(posts_dir, d))]
        if not directories:
            raise Exception("No post directories found")
            
        latest_dir = max(directories)
        full_output_path = os.path.join(posts_dir, latest_dir, 'full_output.txt')
        
        if not os.path.exists(full_output_path):
            raise Exception("No full_output.txt found in latest directory")
            
        with open(full_output_path, 'r') as f:
            content = f.read()
        
        # Print content for debugging
        print("Found content:", content[:500], "...")
        
        try:
            # First try exact markers
            if '---POST START---' in content and '---POST END---' in content:
                post_content = content.split('---POST START---')[1].split('---POST END---')[0]
            else:
                # If content looks like a LinkedIn post (has emojis and sections), use it directly
                if '🔥' in content and '#' in content and 'Call to Action:' in content:
                    post_content = content
                else:
                    # Try finding any content between POST markers
                    import re
                    match = re.search(r'---POST.*?START---(.+?)---POST.*?END---', content, re.DOTALL)
                    if match:
                        post_content = match.group(1)
                    else:
                        raise Exception("Could not find valid post content")
            
            # Clean up the content
            post_content = post_content.strip()
            
            # Remove markdown formatting if present
            post_content = post_content.replace('**', '')
            
            # Verify we got some content
            if not post_content.strip():
                raise Exception("Found POST section but it was empty")
            
            return post_content.strip()
            
        except Exception as e:
            print(f"Error extracting post content: {str(e)}")
            print("Content structure:", content.split('---'))
            raise Exception("Could not extract valid post content from the output file")
        
    def format_post(self, content):
        """Format the post content for LinkedIn"""
        # Clean up markdown and initial whitespace
        content = content.replace('**', '')
        
        # Split into lines and clean each line
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        
        # Initialize formatted sections
        formatted_sections = []
        current_section = []
        
        # Common section header indicators
        header_indicators = [
            ':', # Matches "Key Points:", "Summary:", etc.
            '🔥', '💡', '🚀', '🌎', '🤔', '🗣️', '�', # Emoji headers
            'Breaking News',
            'Why',
            'Impact',
            'Take',
            'Question',
            'Call to Action'
        ]
        
        for i, line in enumerate(lines):
            # Skip section markers
            if line.startswith('---'):
                continue
            
            # Check if this line is a header
            is_header = (
                any(indicator in line for indicator in header_indicators) or
                (i > 0 and len(line) <= 50 and line.isupper()) or  # All caps short lines
                (i > 0 and line.endswith(':'))  # Lines ending with colon
            )
            
            # Handle headers
            if is_header:
                if current_section:
                    formatted_sections.append('\n'.join(current_section))
                    current_section = []
                formatted_sections.append(line)
                continue
            
            # Handle bullet points
            if line.startswith('•') or line.startswith('-'):
                if current_section and not current_section[-1].startswith(('•', '-')):
                    formatted_sections.append('\n'.join(current_section))
                    current_section = []
                current_section.append(line)
                continue
            
            # Handle hashtags at the end
            if line.startswith('#'):
                if current_section:
                    formatted_sections.append('\n'.join(current_section))
                    current_section = []
                formatted_sections.append(line)
                continue
            
            # Regular content lines
            current_section.append(line)
        
        # Add any remaining content
        if current_section:
            formatted_sections.append('\n'.join(current_section))
        
        # Join sections with single line spacing
        formatted_text = ''
        for i, section in enumerate(formatted_sections):
            if not section.strip():
                continue
            
            # Add single line break between all sections
            if i > 0:
                formatted_text += '\n'
            formatted_text += section.strip()
        
        # Handle hashtags - keep them with single line break
        if '#' in formatted_text:
            main_content, *hashtag_parts = formatted_text.split('#')
            hashtags = ' #'.join(part.strip() for part in hashtag_parts)
            formatted_text = f"{main_content.strip()}\n#{hashtags}"
        
        return formatted_text.strip()

def main():
    # Create instance of LinkedInPoster
    poster = LinkedInPoster()
    
    # Post the latest generated content
    success = poster.post_to_linkedin()
    
    if success:
        print("Post has been published to LinkedIn!")
    else:
        print("Failed to post to LinkedIn. Check the error message above.")

if __name__ == "__main__":
    main() 