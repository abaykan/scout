import requests
from bs4 import BeautifulSoup
import logging
from typing import List, Dict, Optional
import time
import re

class BugcrowdScraper:
    """Scraper for Bugcrowd public programs"""
    
    def __init__(self):
        self.base_url = "https://bugcrowd.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logger = logging.getLogger(__name__)
    
    def fetch_programs(self, specific_urls: List[str] = None) -> List[Dict]:
        """
        Fetch Bugcrowd programs. If specific_urls provided, only scrape those.
        Otherwise, try to find public programs (limited without auth).
        """
        programs = []
        
        if specific_urls:
            # Scrape specific program URLs
            for program_url in specific_urls:
                program_data = self._scrape_program_page(program_url)
                if program_data:
                    programs.append(program_data)
                    time.sleep(1)  # Be respectful with requests
        else:
            # No specific URLs provided and no fallback implemented
            self.logger.warning("No specific program URLs provided and public program discovery not implemented")
        
        return programs
    
    def _scrape_program_page(self, program_url: str) -> Optional[Dict]:
        """Scrape individual program page for scope information using JSON API"""
        try:
            # First get the main program page to find changelog ID
            response = self.session.get(program_url, timeout=10)
            response.raise_for_status()
            
            # Extract changelog ID from the page
            changelog_id = self._extract_changelog_id(response.text)
            
            if not changelog_id:
                self.logger.warning(f"Could not find changelog ID for {program_url}, falling back to HTML parsing")
                return self._scrape_program_page_fallback(program_url, response.text)
            
            # Build JSON API URL
            json_url = f"{program_url}/changelog/{changelog_id}.json"
            self.logger.info(f"Fetching scope from JSON API: {json_url}")
            
            # Fetch scope data from JSON API
            json_response = self.session.get(json_url, timeout=10)
            json_response.raise_for_status()
            
            scope_data = json_response.json()
            scope_items = self._parse_scope_from_json(scope_data)
            
            # Extract program name from main page
            soup = BeautifulSoup(response.text, 'lxml')
            program_name = self._extract_program_name(soup, program_url)
            
            if not program_name:
                self.logger.warning(f"Could not extract program name from {program_url}")
                return None
            
            # Extract published_at from JSON data if available
            published_at = None
            if 'publishedAt' in scope_data:
                published_at = scope_data['publishedAt']
            
            return {
                'platform': 'bugcrowd',
                'program_name': program_name,
                'program_url': program_url,
                'scope': scope_items,
                'scope_text': "\n".join([item['target'] for item in scope_items]),  # For display
                'last_checked': int(time.time()),
                'published_at': published_at
            }
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to scrape {program_url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error scraping {program_url}: {e}")
            return None
    
    def _scrape_program_page_fallback(self, program_url: str, html_content: str) -> Optional[Dict]:
        """Fallback method using HTML parsing if JSON API fails"""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract program name
            program_name = self._extract_program_name(soup, program_url)
            
            # Extract scope information
            scope = self._extract_scope(soup)
            
            if not program_name:
                self.logger.warning(f"Could not extract program name from {program_url}")
                return None
            
            return {
                'platform': 'bugcrowd',
                'program_name': program_name,
                'program_url': program_url,
                'scope': scope,
                'scope_text': "\n".join([item['target'] for item in scope]),
                'last_checked': int(time.time())
            }
        except Exception as e:
            self.logger.error(f"Fallback scraping failed for {program_url}: {e}")
            return None
    
    def _extract_changelog_id(self, html_content: str) -> Optional[str]:
        """Extract changelog ID from HTML content"""
        # Look for changelog pattern in the HTML
        pattern = r'changelog/([a-f0-9-]{36})[^a-f0-9-]'
        match = re.search(pattern, html_content)
        if match:
            return match.group(1)
        
        # Alternative pattern if first one doesn't match
        pattern2 = r'changelog/([a-f0-9-]+)'
        match2 = re.search(pattern2, html_content)
        if match2:
            return match2.group(1)
        
        return None
    
    def _parse_scope_from_json(self, json_data: Dict) -> List[Dict]:
        """Parse scope information from JSON API response"""
        scope_items = []
        
        try:
            # Extract from the correct JSON structure based on the example
            # Structure: data -> scope -> targets -> uri/name
            if 'data' in json_data and 'scope' in json_data['data']:
                scope_sections = json_data['data']['scope']
                
                for scope_section in scope_sections:
                    if 'targets' in scope_section:
                        for target in scope_section['targets']:
                            # Prefer URI if available, otherwise use name
                            target_value = target.get('uri') or target.get('name')
                            
                            if target_value and self._looks_like_target(target_value):
                                scope_items.append({
                                    'target': target_value,
                                    'is_wildcard': target_value.startswith('*.') or '*' in target_value,
                                    'domain': self._extract_domain_from_target(target_value)
                                })
            
            self.logger.info(f"Found {len(scope_items)} scope items from JSON")
            
            # Debug: log first few items
            for item in scope_items[:5]:
                self.logger.debug(f"Scope item: {item['target']}")
            
        except Exception as e:
            self.logger.error(f"Error parsing JSON scope: {e}")
        
        # Remove duplicates
        unique_scope = []
        seen = set()
        for item in scope_items:
            if item['target'] not in seen:
                seen.add(item['target'])
                unique_scope.append(item)
        
        return unique_scope
    
    def _extract_program_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract program name from page"""
        # Try multiple selectors for program name
        selectors = [
            'h1.bc-panel__title',
            'h1.program-header__title',
            'h1',
            'title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                # Clean up the text
                if '|' in text:
                    text = text.split('|')[0].strip()
                if 'Bugcrowd' in text:
                    text = text.replace('Bugcrowd', '').strip()
                if text and len(text) > 3:
                    return text
        
        # Fallback: extract from URL
        if '/bugcrowd.com/' in url:
            parts = url.rstrip('/').split('/')
            if len(parts) >= 4:
                return parts[-1].replace('-', ' ').title()
        
        return "Unknown Program"
    
    def _extract_scope(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract scope information from program page and return structured data"""
        scope_items = []
        
        # Try to find scope sections with targets
        scope_selectors = [
            '.bc-panel--scope',
            '.scope-container',
            '.targets-container',
            '[data-test*="scope"]',
            '[class*="scope"]',
            '[class*="target"]'
        ]
        
        for selector in scope_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Look for target elements within scope sections
                targets = element.find_all(['li', 'div', 'span', 'p', 'a'])
                for target in targets:
                    text = target.get_text().strip()
                    if text and self._looks_like_target(text):
                        scope_items.append({
                            'target': text,
                            'is_wildcard': text.startswith('*.') or '*' in text,
                            'domain': self._extract_domain_from_target(text)
                        })
        
        # If no structured scope found, try to extract from any text
        if not scope_items:
            text_content = soup.get_text()
            # Look for common scope patterns
            scope_patterns = [
                r'(?:\*\.)?[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+',
                r'https?://[^\s]+',
                r'[\w.-]+\.[a-zA-Z]{2,}'
            ]
            
            for pattern in scope_patterns:
                matches = re.findall(pattern, text_content)
                for match in matches:
                    if self._looks_like_target(match):
                        clean_match = match.strip()
                        scope_items.append({
                            'target': clean_match,
                            'is_wildcard': clean_match.startswith('*.') or '*' in clean_match,
                            'domain': self._extract_domain_from_target(clean_match)
                        })
        
        # Remove duplicates
        unique_scope = []
        seen = set()
        for item in scope_items:
            if item['target'] not in seen:
                seen.add(item['target'])
                unique_scope.append(item)
        
        return unique_scope
    
    def _extract_domain_from_target(self, target: str) -> str:
        """Extract base domain from target"""
        # Remove protocol and paths
        clean_target = re.sub(r'^https?://', '', target)
        clean_target = re.sub(r'/.*$', '', clean_target)
        
        # Remove wildcard prefix
        clean_target = re.sub(r'^\*\.', '', clean_target)
        
        return clean_target
    
    def _looks_like_target(self, text: str) -> bool:
        """Check if text looks like a target (domain, URL, etc.)"""
        text = text.lower().strip()
        patterns = [
            r'^https?://',
            r'^\*\.',
            r'^[a-z0-9.-]+\.[a-z]{2,}',
            r'\.com$',
            r'\.net$',
            r'\.org$',
            r'\.io$',
            r'target',
            r'scope',
            r'domain',
            r'subdomain'
        ]
        
        return any(re.search(pattern, text) for pattern in patterns)
    
# Standard platform interface
def fetch_programs(config: Dict = None) -> List[Dict]:
    """Standard interface for fetching programs"""
    scraper = BugcrowdScraper()
    specific_urls = config.get('programs_to_monitor', []) if config else None
    return scraper.fetch_programs(specific_urls)