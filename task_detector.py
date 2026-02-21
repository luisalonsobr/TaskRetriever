import json
import requests
from datetime import datetime
from typing import Dict, Optional
from config import OLLAMA_MODEL, OLLAMA_URL, TASK_PROMPT

class OllamaError(Exception):
    """Custom exception for Ollama-related errors."""
    pass

class TaskDetector:
    def __init__(self):
        self.ollama_url = OLLAMA_URL
        self.model = OLLAMA_MODEL
        
        # Test connection on initialization
        if not self._test_ollama_availability():
            print("⚠️ Warning: Ollama is not available. Task detection will be disabled.")
            self._ollama_available = False
        else:
            self._ollama_available = True
        
    def detect_task(self, message: Dict) -> Optional[Dict]:
        """Analyze a message for tasks using Ollama"""
        # Check if Ollama is available
        if not self._ollama_available:
            # Try to reconnect once per detection attempt
            if not self._test_ollama_availability():
                print("⚠️ Ollama still not available, skipping task detection")
                return None
            else:
                print("✅ Ollama reconnected successfully")
                self._ollama_available = True
        
        try:
            # Format the prompt with message data
            prompt = TASK_PROMPT.format(
                message=message['content'],
                sender=message['sender'],
                timestamp=self._format_timestamp(message['timestamp'])
            )
            
            # Call Ollama API
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                # qwen3 often emits reasoning text unless thinking is disabled.
                "think": False,
                # Force structured output instead of free-form explanation.
                "format": "json",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 220
                }
            }

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=30
            )

            # Backward compatibility for Ollama versions that may not support
            # `think` or `format`.
            if response.status_code == 400:
                fallback_payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 300
                    }
                }
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json=fallback_payload,
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
                        return self._normalize_task_data(task_data)
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
                            return self._normalize_task_data(task_data)
                except:
                    pass
                    
                print(f"Failed to parse Ollama response: {llm_response}")
                return None
                
        except requests.RequestException as e:
            print(f"Error calling Ollama: {e}")
            # Mark as unavailable for future checks
            self._ollama_available = False
            return None
        except Exception as e:
            print(f"Unexpected error in task detection: {e}")
            return None
            
        return None

    def _normalize_task_data(self, task_data: Dict) -> Dict:
        """Normalize model output into expected internal representation."""
        normalized = dict(task_data)

        # Some models return the string "null" instead of JSON null.
        deadline = normalized.get("deadline")
        if isinstance(deadline, str) and deadline.strip().lower() in {"null", "none", ""}:
            normalized["deadline"] = None

        priority = normalized.get("priority")
        if isinstance(priority, str):
            p = priority.strip().lower()
            if p in {"alta", "high"}:
                normalized["priority"] = "alta"
            elif p in {"baixa", "low"}:
                normalized["priority"] = "baixa"
            elif p in {"media", "média", "medium"}:
                normalized["priority"] = "média"

        return normalized
    
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
    
    def _test_ollama_availability(self) -> bool:
        """Test if Ollama is running and our model is available (with shorter timeout)"""
        try:
            # Quick health check with short timeout
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            if response.status_code != 200:
                return False
                
            # Check if our model is available
            models = response.json().get('models', [])
            model_names = [model['name'] for model in models]
            
            available = any(self.model in name for name in model_names)
            if not available:
                print(f"⚠️ Model '{self.model}' not found in Ollama. Available models: {model_names}")
            
            return available
            
        except requests.RequestException:
            return False
        except Exception:
            return False
    
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
