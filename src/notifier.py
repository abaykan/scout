import requests
import logging
from typing import List, Dict

class TelegramNotifier:
    """Telegram notification system for S.C.O.U.T"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(__name__)
    
    def send_message(self, message: str, parse_mode: str = "HTML"):
        """Send a message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            self.logger.info("Telegram message sent successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def notify_new_subdomains_grouped(self, subdomains: List[str], program_slug: str, program_data: Dict = None):
        """Send notification about new subdomains grouped by program"""
        if not subdomains:
            return
            
        # Create message header
        message = f"🔍 <b>S.C.O.U.T - New Subdomains Found</b>\n\n"
        message += f"<b>Program:</b> {program_slug}\n"
        
        if program_data:
            message += f"<b>URL:</b> {program_data.get('program_url', 'N/A')}\n"
            message += f"<b>Last Checked:</b> {program_data.get('last_checked', 'N/A')}\n\n"
        
        # Add subdomains (limit to avoid message too long)
        max_subdomains = 20
        if len(subdomains) > max_subdomains:
            message += f"<b>Found {len(subdomains)} new subdomains (showing first {max_subdomains}):</b>\n"
            subdomains = subdomains[:max_subdomains]
        else:
            message += f"<b>Found {len(subdomains)} new subdomains:</b>\n"
        
        for i, subdomain in enumerate(subdomains, 1):
            message += f"{i}. {subdomain}\n"
        
        if len(subdomains) > max_subdomains:
            message += f"\n... and {len(subdomains) - max_subdomains} more subdomains"
        
        self.send_message(message)
    
    def notify_monitoring_started(self):
        """Send notification when monitoring starts"""
        message = """
✅ <b>S.C.O.U.T Monitoring Started</b>

Monitoring is now active and will notify you of:
• New bug bounty programs
• Scope changes in existing programs  
• New subdomain discoveries

Stay tuned for updates! 🚀
        """
        self.send_message(message.strip())

def create_notifier(notifier_type: str, config: Dict = None):
    """Create notifier instance based on type"""
    if notifier_type == "telegram" and config:
        try:
            bot_token = config.get('telegram', {}).get('bot_token')
            chat_id = config.get('telegram', {}).get('chat_id')
            
            if bot_token and chat_id:
                return TelegramNotifier(bot_token, chat_id)
            else:
                logging.getLogger(__name__).warning("Telegram credentials missing in config")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to create Telegram notifier: {e}")
    
    return None
