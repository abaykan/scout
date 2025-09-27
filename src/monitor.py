import importlib
import time
import logging
import re
from typing import Dict, List, Any
import json
import os
from .db import Database
from .utils import SubdomainScanner
from .notifier import create_notifier

class SCOUTMonitor:
    """Core monitoring system for S.C.O.U.T"""
    
    def __init__(self, config_path='config.json'):
        self.config = self._load_config(config_path)
        self.db = Database(config_path)
        self.platforms = {}
        self.scanner = SubdomainScanner()
        self.logger = self._setup_logging()
        self.notifier = self._setup_notifier()
        self._load_platforms()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise Exception(f"Error loading config: {e}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration - only if not already configured"""
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('scout.log'),
                    logging.StreamHandler()
                ]
            )
        return logging.getLogger(__name__)
    
    def _setup_notifier(self):
        """Setup notification system"""
        notifier_type = self.config.get('notifications', {}).get('type', 'telegram')
        notifier = create_notifier(notifier_type)
        
        if notifier:
            self.logger.info(f"Notifier configured: {notifier_type}")
        else:
            self.logger.warning(f"Notifier {notifier_type} not configured or failed to initialize")
        
        return notifier

    def _load_platforms(self):
        """Load and initialize enabled platforms"""
        enabled_platforms = self.config.get('platforms', {})
        
        for platform_name, platform_config in enabled_platforms.items():
            if platform_config.get('enabled', False):
                try:
                    # Try to import the platform module
                    module = importlib.import_module(f"src.platforms.{platform_name}")
                    
                    # Store platform functions (only fetch_programs, reports removed)
                    self.platforms[platform_name] = {
                        'fetch_programs': getattr(module, 'fetch_programs', None),
                        'config': platform_config
                    }
                    
                    self.logger.info(f"Loaded platform: {platform_name}")
                    
                except ImportError as e:
                    self.logger.warning(f"Platform {platform_name} not available: {e}")
                except Exception as e:
                    self.logger.error(f"Error loading platform {platform_name}: {e}")
    
    def monitor_programs(self):
        """Monitor all enabled platforms for program changes"""
        self.logger.info("Starting program monitoring...")
        
        # Database connection is managed by the class instance
        if not self.db.connection or not self.db.connection.is_connected():
            if not self.db.connect():
                self.logger.error("Failed to connect to database")
                return
        
        try:
            for platform_name, platform_data in self.platforms.items():
                fetch_func = platform_data.get('fetch_programs')
                platform_config = platform_data.get('config', {})
                
                if fetch_func:
                    self.logger.info(f"Monitoring programs for {platform_name}")
                    programs = fetch_func(platform_config)
                    
                    for program in programs:
                        if program:  # Ensure program data is not None
                            self.logger.debug(f"Processing program: {program.get('program_name')}")
                            self._save_program(platform_name, program)
                        else:
                            self.logger.warning("Received None program data from platform")
                
                time.sleep(1)  # Be respectful between platforms
            
        except Exception as e:
            self.logger.error(f"Error during program monitoring: {e}")
    
    def _save_program(self, platform: str, program_data: Dict):
        """Save program data to database and process all domains into single program file"""
        # Extract all domains for processing
        all_domains = []
        if 'scope' in program_data and isinstance(program_data['scope'], list):
            for scope_item in program_data['scope']:
                all_domains.append(scope_item['target'])
        
        # Process all domains and collect results
        if all_domains:
            self.logger.info(f"Found {len(all_domains)} domains to process")
            
            # Separate wildcard and regular domains
            wildcard_domains = []
            regular_domains = []
            
            for domain in all_domains:
                if domain.startswith('*.') or '*' in domain:
                    wildcard_domains.append(domain)
                else:
                    regular_domains.append(domain)
            
            # Collect all subdomains to save
            all_subdomains_to_save = []
            
            # Scan wildcard domains if any
            if wildcard_domains:
                self.logger.info(f"Found {len(wildcard_domains)} wildcard domains to scan")
                scan_results = self.scanner.scan_wildcard_domains(wildcard_domains, "scans")
                
                # Collect subdomains from wildcard scans
                for domain, subdomains in scan_results.items():
                    if subdomains:
                        all_subdomains_to_save.extend(subdomains)
                        self.logger.info(f"Found {len(subdomains)} subdomains for {domain}")
            
            # Add regular domains to the list
            if regular_domains:
                self.logger.info(f"Found {len(regular_domains)} regular domains")
                all_subdomains_to_save.extend(regular_domains)
            
            # Save all subdomains to a single file named after the program slug
            if all_subdomains_to_save:
                # Extract program slug from URL (e.g., 'nasa-vdp' from 'https://bugcrowd.com/engagements/nasa-vdp')
                program_slug = self._extract_program_slug_from_url(program_data['program_url'])
                
                filename = f"scans/{program_slug}.txt"
                
                # Remove duplicates and sort
                unique_subdomains = sorted(set(all_subdomains_to_save))
                
                # Save to file
                self.scanner.save_subdomains_to_file(unique_subdomains, filename)
                self.logger.info(f"Saved {len(unique_subdomains)} total subdomains for program {program_data['program_name']} to {filename}")
        
        # Save program to database
        query = """
        INSERT INTO programs (platform, program_name, program_url, scope, last_checked, published_at)
        VALUES (%s, %s, %s, %s, FROM_UNIXTIME(%s), %s)
        ON DUPLICATE KEY UPDATE
            scope = VALUES(scope),
            last_checked = VALUES(last_checked),
            published_at = VALUES(published_at)
        """
        
        # Convert scope to text for database storage
        scope_text = program_data.get('scope_text', '')
        if not scope_text and 'scope' in program_data:
            if isinstance(program_data['scope'], list):
                scope_text = "\n".join([item.get('target', '') for item in program_data['scope']])
            else:
                scope_text = str(program_data['scope'])
        
        # Extract program slug for database storage
        program_slug = self._extract_program_slug_from_url(program_data['program_url'])
        
        # Handle published_at timestamp
        published_at = program_data.get('published_at')
        if published_at:
            # Convert ISO format to MySQL datetime format
            try:
                from datetime import datetime
                published_at_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                published_at_mysql = published_at_dt.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                published_at_mysql = None
        else:
            published_at_mysql = None

        params = (
            platform,
            program_slug,  # Use program slug instead of full program name
            program_data['program_url'],
            scope_text,
            program_data.get('last_checked', int(time.time())),
            published_at_mysql
        )
        
        result = self.db.execute_query(query, params)
        if result == 1:
            self.logger.info(f"New program added: {program_slug}")
        elif result == 2:
            self.logger.debug(f"Program updated: {program_slug}")
        else:
            self.logger.warning(f"Failed to save program: {program_slug}")
    
    # Report monitoring removed as requested - reports table no longer exists
    
    def monitor_subdomains(self, file_paths: List[str] = None):
        """Monitor subdomains from text files including scan results"""
        self.logger.info("Starting subdomain monitoring...")
        
        # Use existing connection if available
        if not self.db.connection or not self.db.connection.is_connected():
            if not self.db.connect():
                self.logger.error("Failed to connect to database")
                return
        
        try:
            if file_paths is None:
                # Default file patterns to look for - now includes scans directory
                file_paths = [
                    'subdomains.txt',
                    '*.subdomains.txt',
                    'results/*.txt',
                    'scans/*.txt'  # Add scans directory
                ]
            
            subdomains_found = self._read_subdomain_files(file_paths)
            new_subdomains = self._find_new_subdomains(subdomains_found)
            
            if new_subdomains:
                self.logger.info(f"Found {len(new_subdomains)} new subdomains")
                self._alert_new_subdomains(new_subdomains)
            else:
                self.logger.info("No new subdomains found")
                
        except Exception as e:
            self.logger.error(f"Error during subdomain monitoring: {e}")
    
    def _read_subdomain_files(self, file_patterns: List[str]) -> List[str]:
        """Read subdomains from text files"""
        import glob
        subdomains = []
        
        for pattern in file_patterns:
            for file_path in glob.glob(pattern):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            subdomain = line.strip()
                            if subdomain and self._is_valid_subdomain(subdomain):
                                subdomains.append((subdomain, file_path))
                    self.logger.debug(f"Read subdomains from {file_path}")
                except Exception as e:
                    self.logger.warning(f"Error reading {file_path}: {e}")
        
        return subdomains
    
    def _is_valid_subdomain(self, domain: str) -> bool:
        """Check if a string looks like a valid subdomain or contains a valid domain"""
        # First, try to extract domain from URL if it contains protocol
        if '://' in domain:
            # Extract domain part from URL
            domain = self._extract_domain_from_url(domain)
        
        # Check if it's a valid domain pattern
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain)) and '.' in domain

    def _extract_domain_from_url(self, url: str) -> str:
        """Extract domain from URL (remove protocol and paths)"""
        # Remove protocol
        domain = re.sub(r'^https?://', '', url)
        # Remove paths and query parameters
        domain = re.sub(r'/.*$', '', domain)
        # Remove port numbers
        domain = re.sub(r':\d+$', '', domain)
        return domain.strip()
    
    def _find_new_subdomains(self, current_subdomains: List[tuple]) -> List[tuple]:
        """Find subdomains that are new (not in database)"""
        new_subdomains = []
        
        for subdomain, source_file in current_subdomains:
            # Extract program slug from filename (e.g., 'intercom' from 'scans/intercom.txt')
            program_slug = self._extract_program_slug_from_filename(source_file)
            
            # Check if subdomain exists in database
            query = "SELECT id FROM subdomains WHERE subdomain = %s"
            result = self.db.execute_query(query, (subdomain,))
            
            if not result:  # Subdomain not found
                new_subdomains.append((subdomain, program_slug))
                # Insert new subdomain
                insert_query = """
                INSERT INTO subdomains (subdomain, source, is_new)
                VALUES (%s, %s, TRUE)
                """
                self.db.execute_query(insert_query, (subdomain, program_slug))
            else:
                # Update last seen timestamp
                update_query = "UPDATE subdomains SET last_seen = CURRENT_TIMESTAMP, is_new = FALSE WHERE subdomain = %s"
                self.db.execute_query(update_query, (subdomain,))
        
        return new_subdomains

    def _extract_program_slug_from_filename(self, filename: str) -> str:
        """Extract program slug from filename (e.g., 'intercom' from 'scans/intercom.txt')"""
        import os
        # Get basename without extension
        basename = os.path.basename(filename)
        if '.' in basename:
            return basename.split('.')[0]
        return basename
    
    def _extract_program_slug_from_url(self, program_url: str) -> str:
        """Extract program slug from URL (e.g., 'nasa-vdp' from 'https://bugcrowd.com/engagements/nasa-vdp')"""
        import re
        # Extract the last part of the URL after the last slash
        slug_match = re.search(r'/([^/]+)/?$', program_url)
        if slug_match:
            slug = slug_match.group(1)
            
            # Handle HackerOne URLs - they use direct handle names
            if 'hackerone.com' in program_url:
                return slug  # For HackerOne, the slug is the handle itself
            
            # Handle YesWeHack URLs - extract from programs path
            if 'yeswehack.com/programs/' in program_url:
                return slug  # For YesWeHack, the slug is the program name
            
            # For Bugcrowd, remove 'engagements-' prefix if present
            if slug.startswith('engagements-'):
                slug = slug.replace('engagements-', '')
            
            return slug
        
        # Fallback: use a default name
        return 'unknown-program'


    def _alert_new_subdomains(self, new_subdomains: List[tuple]):
        """Alert about new subdomains using notifier - grouped by program"""
        if not new_subdomains:
            return
            
        # Group subdomains by program source
        subdomains_by_program = {}
        for subdomain, source in new_subdomains:
            if source not in subdomains_by_program:
                subdomains_by_program[source] = []
            subdomains_by_program[source].append(subdomain)
        
        # Log summary
        self.logger.info(f"Found new subdomains in {len(subdomains_by_program)} programs")
        
        # Send grouped notifications
        if self.notifier:
            for program_slug, subdomains in subdomains_by_program.items():
                try:
                    # Get program data for this source
                    program_data = self._get_program_data_by_slug(program_slug)
                    
                    # Send single notification with all subdomains for this program
                    self.notifier.notify_new_subdomains_grouped(subdomains, program_slug, program_data)
                    
                    # Small delay between program notifications
                    time.sleep(0.5)
                except Exception as e:
                    self.logger.error(f"Failed to send notification for program {program_slug}: {e}")
        else:
            self.logger.warning("Notifier not available - skipping subdomain notifications")
    
    def _get_program_data_by_slug(self, program_slug: str) -> Dict:
        """Get program data by program slug from database"""
        # Use existing connection if available
        if not self.db.connection or not self.db.connection.is_connected():
            if not self.db.connect():
                return None
                
        try:
            query = "SELECT program_name, program_url, last_checked, published_at FROM programs WHERE program_name = %s"
            result = self.db.execute_query(query, (program_slug,))
            
            if result:
                # Handle NULL values for published_at
                published_at = result[0]['published_at']
                if published_at:
                    published_at_str = published_at.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    published_at_str = 'Unknown'
                
                program_data = {
                    'program_name': result[0]['program_name'],
                    'program_url': result[0]['program_url'],
                    'last_checked': result[0]['last_checked'].strftime('%Y-%m-%d %H:%M:%S') if result[0]['last_checked'] else 'Unknown',
                    'published_at': published_at_str
                }
                return program_data
            return None
        except Exception as e:
            self.logger.error(f"Error getting program data for {program_slug}: {e}")
            return None

    def run_once(self):
        """Run all monitoring tasks once"""
        self.logger.info("Running one-time monitoring...")
        try:
            self.monitor_programs()
            self.monitor_subdomains()
            self.logger.info("One-time monitoring completed")
        finally:
            # Ensure database connection is closed
            if hasattr(self, 'db') and self.db.connection and self.db.connection.is_connected():
                self.db.disconnect()

if __name__ == "__main__":
    monitor = SCOUTMonitor()
    monitor.run_once()