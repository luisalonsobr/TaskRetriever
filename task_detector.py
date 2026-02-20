import json
import requests
from datetime import datetime
from typing import Dict, Optional
from config import OLLAMA_MODEL, OLLAMA_URL, TASK_PROMPT

class TaskDetector:
    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.model = OLLAMA_MODEL
        
    def detect_task(self, message: Dict) -> Optional[Dict]:
        """Analyze a message for tasks using Ollama"""
        try:
            # Format the prompt with message data
            prompt = TASK_PROMPT.format(
                message=message['content'],
                sender=message['sender'],
                timestamp=self._format_timestamp(message['timestamp'])
            )
            
            # Call Ollama API
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistent parsing
                        "num_predict": 200   # Limit response length
                    }
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Ollama API error: {response.status_code}")
                return None
                
            result = response.json()
            llm_response = result.get('response', '').strip()
            
            # Parse the JSON response
            try:
                task_data = json.loads(llm_response)
                
                # Validate response format
                if isinstance(task_data, dict) and 'has_task' in task_data:
                    if task_data['has_task']:
                        # Ensure required fields exist
                        if 'task_description' not in task_data:
                            return None
                        return task_data
                    else:
                        return None
                        
            except json.JSONDecodeError:
                # Try to extract JSON from response if it's wrapped in text
                try:
                    start = llm_response.find('{')
                    end = llm_response.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_part = llm_response[start:end]
                        task_data = json.loads(json_part)
                        if task_data.get('has_task'):
                            return task_data
                except:
                    pass
                    
                print(f"Failed to parse Ollama response: {llm_response}")
                return None
                
        except requests.RequestException as e:
            print(f"Error calling Ollama: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in task detection: {e}")
            return None
            
        return None
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            # Convert Unix timestamp to readable format
            if timestamp.isdigit():
                dt = datetime.fromtimestamp(int(timestamp))
                return dt.strftime("%d/%m/%Y %H:%M")
            return timestamp
        except:
            return timestamp
    
    def test_connection(self) -> bool:
        """Test if Ollama is running and model is available"""
        try:
            # Check if Ollama is running
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code != 200:
                return False
                
            # Check if our model is available
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            
            return any(self.model in name for name in model_names)
            
        except requests.RequestException:
            return False