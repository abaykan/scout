import requests
import logging
import time
from typing import List, Dict, Optional
import re

class HackerOneScraper:
    """Scraper for HackerOne programs using GraphQL API"""
    
    def __init__(self):
        self.base_url = "https://hackerone.com"
        self.graphql_url = "https://hackerone.com/graphql"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://hackerone.com',
            'Sec-GPC': '1'
        })
        self.logger = logging.getLogger(__name__)
    
    def fetch_programs(self, specific_urls: List[str] = None) -> List[Dict]:
        """
        Fetch HackerOne programs. If specific_urls provided, only scrape those.
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
        """Scrape individual HackerOne program for scope information"""
        try:
            # Extract handle from URL
            handle = self._extract_handle_from_url(program_url)
            if not handle:
                self.logger.warning(f"Could not extract handle from URL: {program_url}")
                return None
            
            # Fetch scope data from GraphQL API
            scope_data = self._fetch_scope_from_graphql(handle)
            if not scope_data:
                return None
            
            # Extract program name from handle
            program_name = self._format_program_name(handle)
            
            return {
                'platform': 'hackerone',
                'program_name': program_name,
                'program_url': program_url,
                'scope': scope_data,
                'scope_text': "\n".join([item['target'] for item in scope_data]),
                'last_checked': int(time.time()),
                'published_at': None  # HackerOne doesn't provide published_at in the API
            }
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to scrape {program_url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error scraping {program_url}: {e}")
            return None
    
    def _extract_handle_from_url(self, url: str) -> Optional[str]:
        """Extract handle from HackerOne URL"""
        # Pattern: https://hackerone.com/{handle}
        pattern = r'https?://hackerone\.com/([a-zA-Z0-9_-]+)'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
    
    def _fetch_scope_from_graphql(self, handle: str) -> List[Dict]:
        """Fetch scope data from HackerOne GraphQL API"""
        query = """
        query PolicySearchStructuredScopesQuery($handle: String!, $searchString: String, $eligibleForSubmission: Boolean, $eligibleForBounty: Boolean, $asmTagIds: [Int], $assetTypes: [StructuredScopeAssetTypeEnum!], $from: Int, $size: Int, $sort: SortInput) {
          team(handle: $handle) {
            id
            team_display_options {
              show_total_reports_per_asset
              __typename
            }
            structured_scopes_search(
              search_string: $searchString
              eligible_for_submission: $eligibleForSubmission
              eligible_for_bounty: $eligibleForBounty
              asm_tag_ids: $asmTagIds
              asset_types: $assetTypes
              from: $from
              size: $size
              sort: $sort
            ) {
              nodes {
                ... on StructuredScopeDocument {
                  id
                  ...PolicyScopeStructuredScopeDocument
                  __typename
                }
                __typename
              }
              pageInfo {
                startCursor
                hasPreviousPage
                endCursor
                hasNextPage
                __typename
              }
              total_count
              __typename
            }
            __typename
          }
        }

        fragment PolicyScopeStructuredScopeDocument on StructuredScopeDocument {
          id
          identifier
          display_name
          instruction
          cvss_score
          eligible_for_bounty
          eligible_for_submission
          asm_system_tags
          created_at
          updated_at
          total_resolved_reports
          attachments {
            id
            file_name
            file_size
            content_type
            expiring_url
            __typename
          }
          __typename
        }
        """
        
        variables = {
            "handle": handle,
            "searchString": "",
            "eligibleForSubmission": True,  # Only targets eligible for submission
            "eligibleForBounty": True,      # Only targets eligible for bounty
            "asmTagIds": [],
            "assetTypes": [],
            "from": 0,
            "size": 100,
            "sort": {
                "field": "cvss_score",
                "direction": "DESC"
            }
        }
        
        payload = {
            "operationName": "PolicySearchStructuredScopesQuery",
            "variables": variables,
            "query": query
        }
        
        try:
            response = self.session.post(self.graphql_url, json=payload, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_scope_from_graphql(data)
            
        except requests.RequestException as e:
            self.logger.error(f"GraphQL request failed for handle {handle}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error parsing GraphQL response for handle {handle}: {e}")
            return []
    
    def _parse_scope_from_graphql(self, data: Dict) -> List[Dict]:
        """Parse scope information from GraphQL response"""
        scope_items = []
        
        try:
            # Extract scope nodes from the response
            nodes = data.get('data', {}).get('team', {}).get('structured_scopes_search', {}).get('nodes', [])
            
            for node in nodes:
                identifier = node.get('identifier', '')
                display_name = node.get('display_name', '')
                
                # Only include targets that are eligible for both submission and bounty
                eligible_for_submission = node.get('eligible_for_submission', False)
                eligible_for_bounty = node.get('eligible_for_bounty', False)
                if not (eligible_for_submission and eligible_for_bounty):
                    continue
                
                # Clean and validate the target
                target = identifier.strip()
                if not self._looks_like_target(target):
                    continue
                
                scope_items.append({
                    'target': target,
                    'is_wildcard': target.startswith('*.') or '*' in target,
                    'domain': self._extract_domain_from_target(target),
                    'asset_type': display_name.lower()
                })
            
            self.logger.info(f"Found {len(scope_items)} scope items from HackerOne")
            
            # Debug: log first few items
            for item in scope_items[:5]:
                self.logger.debug(f"HackerOne scope item: {item['target']} ({item['asset_type']})")
            
        except Exception as e:
            self.logger.error(f"Error parsing GraphQL scope data: {e}")
        
        # Remove duplicates
        unique_scope = []
        seen = set()
        for item in scope_items:
            if item['target'] not in seen:
                seen.add(item['target'])
                unique_scope.append(item)
        
        return unique_scope
    
    def _format_program_name(self, handle: str) -> str:
        """Format handle into a readable program name"""
        # Convert underscores and dashes to spaces, then title case
        name = handle.replace('_', ' ').replace('-', ' ').title()
        return name
    
    def _extract_domain_from_target(self, target: str) -> str:
        """Extract base domain from target"""
        import re
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
            r'\.app$',
            r'\.dev$'
        ]
        
        return any(re.search(pattern, text) for pattern in patterns)

# Standard platform interface
def fetch_programs(config: Dict = None) -> List[Dict]:
    """Standard interface for fetching programs"""
    scraper = HackerOneScraper()
    specific_urls = config.get('programs_to_monitor', []) if config else None
    return scraper.fetch_programs(specific_urls)
