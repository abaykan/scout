import requests
import logging
import time
from typing import List, Dict, Optional
import re
from bs4 import BeautifulSoup

class YesWeHackScraper:
    """Scraper for YesWeHack programs using HTML parsing"""
    
    def __init__(self):
        self.base_url = "https://yeswehack.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        self.logger = logging.getLogger(__name__)
    
    def fetch_programs(self, specific_urls: List[str] = None) -> List[Dict]:
        """
        Fetch YesWeHack programs. If specific_urls provided, only scrape those.
        """
        programs = []
        
        if specific_urls:
            # Scrape specific program URLs
            for program_url in specific_urls:
                program_data = self._scrape_program(program_url)
                if program_data:
                    programs.append(program_data)
                    time.sleep(1)  # Be respectful with requests
        
        return programs
    
    def _scrape_program(self, program_url: str) -> Optional[Dict]:
        """Scrape individual YesWeHack program for scope information"""
        try:
            response = self.session.get(program_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract program name
            program_name = self._extract_program_name(soup, program_url)
            if not program_name:
                self.logger.warning(f"Could not extract program name from {program_url}")
                return None
            
            # Extract scope information
            scope_items = self._extract_scope(soup)
            
            return {
                'platform': 'yeswehack',
                'program_name': program_name,
                'program_url': program_url,
                'scope': scope_items,
                'scope_text': "\n".join([item['target'] for item in scope_items]),
                'last_checked': int(time.time()),
                'published_at': None  # YesWeHack doesn't provide published_at in HTML
            }
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to scrape {program_url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error scraping {program_url}: {e}")
            return None
    
    def _extract_program_name(self, soup: BeautifulSoup, url: str) -> str:
        """Extract program name from page"""
        # Try multiple selectors for program name
        selectors = [
            'h1',
            '.program-title',
            '.title',
            'title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                # Clean up the text
                if '|' in text:
                    text = text.split('|')[0].strip()
                if 'YesWeHack' in text:
                    text = text.replace('YesWeHack', '').strip()
                if text and len(text) > 3:
                    return text
        
        # Fallback: extract from URL
        if '/yeswehack.com/programs/' in url:
            parts = url.rstrip('/').split('/')
            if len(parts) >= 5:
                return parts[-1].replace('-', ' ').title()
        
        return "Unknown Program"
    
    def _extract_scope(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract scope information from program page"""
        scope_items = []
        
        # Look for scope tables - based on the HTML structure shown
        scope_tables = soup.select('table')
        
        for table in scope_tables:
            # Look for rows that contain scope information
            rows = table.select('tbody tr') if table.select('tbody') else table.select('tr')
            
            for row in rows:
                # Look for cells that might contain scope targets
                cells = row.select('td')
                if len(cells) >= 2:  # Assuming at least 2 columns: scope and type/severity
                    scope_cell = cells[0]  # First cell likely contains the scope
                    target_text = scope_cell.get_text().strip()
                    
                    # Clean and validate the target
                    if target_text and self._looks_like_target(target_text):
                        scope_items.append({
                            'target': target_text,
                            'is_wildcard': target_text.startswith('*.') or '*' in target_text,
                            'domain': self._extract_domain_from_target(target_text),
                            'asset_type': self._extract_asset_type(cells) if len(cells) > 1 else 'unknown'
                        })
        
        # If no scope found in tables, try other patterns
        if not scope_items:
            # Look for scope sections with lists
            scope_sections = soup.select('[class*="scope"], [class*="target"], [data-test*="scope"]')
            for section in scope_sections:
                # Look for list items or paragraphs that might contain scope
                elements = section.find_all(['li', 'p', 'div', 'span'])
                for element in elements:
                    text = element.get_text().strip()
                    if text and self._looks_like_target(text):
                        scope_items.append({
                            'target': text,
                            'is_wildcard': text.startswith('*.') or '*' in text,
                            'domain': self._extract_domain_from_target(text),
                            'asset_type': 'unknown'
                        })
        
        # Remove duplicates
        unique_scope = []
        seen = set()
        for item in scope_items:
            if item['target'] not in seen:
                seen.add(item['target'])
                unique_scope.append(item)
        
        self.logger.info(f"Found {len(unique_scope)} scope items from YesWeHack")
        
        # Debug: log first few items
        for item in unique_scope[:5]:
            self.logger.debug(f"YesWeHack scope item: {item['target']} ({item['asset_type']})")
        
        return unique_scope
    
    def _extract_asset_type(self, cells: List) -> str:
        """Extract asset type from table cells"""
        if len(cells) > 1:
            # Second cell might contain type/severity information
            type_text = cells[1].get_text().strip().lower()
            if 'web' in type_text or 'application' in type_text:
                return 'web_application'
            elif 'api' in type_text:
                return 'api'
            elif 'mobile' in type_text:
                return 'mobile'
            elif 'server' in type_text:
                return 'server'
        return 'unknown'
    
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
        if not text:
            return False
        
        # Common patterns for scope targets
        patterns = [
            r'^https?://',
            r'^\*\.',
            r'^[a-z0-9.-]+\.[a-z]{2,}',
            r'\.com$',
            r'\.net$',
            r'\.org$',
            r'\.io$',
            r'\.fr$',
            r'\.app$',
            r'\.dev$'
        ]
        
        return any(re.search(pattern, text) for pattern in patterns)

# Standard platform interface
def fetch_programs(config: Dict = None) -> List[Dict]:
    """Standard interface for fetching programs"""
    scraper = YesWeHackScraper()
    specific_urls = config.get('programs_to_monitor', []) if config else None
    return scraper.fetch_programs(specific_urls)