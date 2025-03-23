"""Status checking for Elysium API"""

import logging
import requests
import time
from datetime import datetime
from typing import Dict, Any, Tuple

from api.constants import BASE_API_URL

class StatusChecker:
    """Handles status checking for the Elysium API"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = BASE_API_URL
        self.last_check_time = None
        self.last_status = None
    
    def check_api_status(self) -> Tuple[bool, str]:
        """
        Check if the API is online and responsive
        
        Returns:
            Tuple of (is_online, status_message)
        """
        try:
            # Cache the status for 30 seconds to avoid too many requests
            current_time = time.time()
            if self.last_check_time and current_time - self.last_check_time < 30 and self.last_status is not None:
                return self.last_status
            
            # Use the root endpoint for health check
            response = requests.get(self.base_url, timeout=10)
            
            if response.status_code == 200:
                self.logger.info("API is online and responsive")
                status = (True, "API is online")
            else:
                error_msg = f"API returned status code: {response.status_code}"
                self.logger.warning(error_msg)
                status = (False, error_msg)
                
            # Cache the result
            self.last_check_time = current_time
            self.last_status = status
            return status
                
        except requests.exceptions.ConnectionError:
            error_msg = "Could not connect to API"
            self.logger.error(error_msg)
            status = (False, error_msg)
            
            # Cache the result
            self.last_check_time = current_time
            self.last_status = status
            return status
            
        except requests.exceptions.Timeout:
            error_msg = "Connection to API timed out"
            self.logger.error(error_msg)
            status = (False, error_msg)
            
            # Cache the result
            self.last_check_time = current_time
            self.last_status = status
            return status
            
        except Exception as e:
            error_msg = f"Error checking API status: {str(e)}"
            self.logger.error(error_msg)
            return (False, error_msg)
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """
        Get detailed API status information
        
        Returns:
            Dict with status details
        """
        is_online, message = self.check_api_status()
        
        return {
            "is_online": is_online,
            "message": message,
            "api_url": self.base_url,
            "timestamp": datetime.now().isoformat(),
            "last_check": self.last_check_time
        }
        
    def check_endpoint(self, endpoint: str) -> Tuple[bool, str]:
        """
        Check if a specific API endpoint is working
        
        Args:
            endpoint: API endpoint to check (without base URL)
            
        Returns:
            Tuple of (is_working, status_message)
        """
        try:
            url = self.base_url + endpoint
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                self.logger.info(f"Endpoint {endpoint} is online")
                return (True, "Endpoint is online")
            else:
                error_msg = f"Endpoint returned status code: {response.status_code}"
                self.logger.warning(error_msg)
                return (False, error_msg)
                
        except Exception as e:
            error_msg = f"Error checking endpoint {endpoint}: {str(e)}"
            self.logger.error(error_msg)
            return (False, error_msg)
            
    def run_full_health_check(self) -> Dict[str, Any]:
        """
        Run a full health check on the API
        
        Returns:
            Dict with health check results
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "overall_status": False,
            "endpoints": {}
        }
        
        # First check the root endpoint
        is_online, message = self.check_api_status()
        results["overall_status"] = is_online
        results["root_status"] = {
            "is_online": is_online,
            "message": message
        }
        
        # If the root is not online, no point checking other endpoints
        if not is_online:
            return results
            
        # Check some key endpoints from our API spec
        endpoints_to_check = [
            "/balances",
            "/open-orders"
        ]
        
        for endpoint in endpoints_to_check:
            is_working, message = self.check_endpoint(endpoint)
            results["endpoints"][endpoint] = {
                "is_working": is_working,
                "message": message
            }
            
            # Update overall status - if any critical endpoint fails, overall status is false
            if not is_working:
                results["overall_status"] = False
        
        return results