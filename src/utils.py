"""
Utility functions for S.C.O.U.T
Includes subdomain discovery and other helper functions
"""

import subprocess
import os
import logging
from typing import Dict, List

class SubdomainScanner:
    """Subdomain discovery utility for S.C.O.U.T"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def scan_wildcard_domains(self, domains: List[str], output_dir: str = "scans") -> Dict[str, List[str]]:
        """Scan wildcard domains using subfinder and return results"""
        results = {}
        
        for domain in domains:
            try:
                # Clean domain (remove wildcard prefix)
                clean_domain = domain.replace('*.', '')
                
                # Run subfinder
                cmd = ['subfinder', '-d', clean_domain, '-silent']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    subdomains = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                    results[domain] = subdomains
                    self.logger.info(f"Found {len(subdomains)} subdomains for {domain}")
                else:
                    self.logger.warning(f"Subfinder failed for {domain}: {result.stderr}")
                    results[domain] = []
                    
            except subprocess.TimeoutExpired:
                self.logger.error(f"Subfinder timeout for {domain}")
                results[domain] = []
            except Exception as e:
                self.logger.error(f"Error scanning {domain}: {e}")
                results[domain] = []
        
        return results
    
    def save_subdomains_to_file(self, subdomains: List[str], filename: str):
        """Save subdomains to a text file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                for subdomain in subdomains:
                    f.write(subdomain + '\n')
            
            self.logger.debug(f"Saved {len(subdomains)} subdomains to {filename}")
        except Exception as e:
            self.logger.error(f"Error saving subdomains to {filename}: {e}")