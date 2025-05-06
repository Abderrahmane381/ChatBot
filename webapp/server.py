# webapp/server.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
import json
import re
from wsgiref.simple_server import make_server
from chatbots.generalist import ChatbotGeneralist
from chatbots.arduino_expert import ArduinoExpert
from chatbots.raspberry_expert import RaspberryExpert


# Configuration
API_KEY = "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"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuration des chatbots
CHATBOTS = {
    'generalist': ChatbotGeneralist(
        csv_folder=os.path.join(BASE_DIR, "C:/Users/dell/OneDrive/Desktop/ChatBot/generalist_data"),
        api_key="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"
    ),
    'arduino_expert': ArduinoExpert(
        csv_folder=os.path.join(BASE_DIR, "C:/Users/dell/OneDrive/Desktop/ChatBot/arduino_data"),
        api_key="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"
    ),
    'raspberry_expert': RaspberryExpert(
         csv_folder=os.path.join(BASE_DIR, "C:/Users/dell/OneDrive/Desktop/ChatBot/raspberry_data"),
         api_key="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"
    )
}

current_bot = CHATBOTS['generalist']

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def sanitize_response(response):
    """Nettoie et formate la réponse pour éviter les problèmes d'affichage"""
    # Supprimer toute balise HTML
    clean = re.sub(r'<[^>]+>', '', response)
    
    # Assurer un formatage markdown cohérent
    # Convertir les listes mal formatées en listes propres
    clean = re.sub(r'(?m)^(\s*)-\s+', r'\1- ', clean)
    
    # Assurer qu'il n'y a pas trop de lignes vides consécutives
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    
    # Vérifier la présence potentielle d'hallucination typique
    hallucination_indicators = [
        "comme mentionné dans la documentation",
        "selon la documentation",
        "d'après le manuel",
        "comme indiqué dans les spécifications"
    ]
    
    has_potential_hallucination = any(indicator in clean.lower() for indicator in hallucination_indicators)
    
    if has_potential_hallucination:
        clean += "\n\n[Note: Cette réponse pourrait contenir des informations non vérifiées. Veuillez consulter la documentation officielle pour confirmation.]"
    
    return clean

def app(env, start_response):
    global current_bot
    try:
        path = env.get('PATH_INFO', '/')
        method = env.get('REQUEST_METHOD', '')

        if path == '/' and method == 'GET':
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
            with open(os.path.join(BASE_DIR, 'templates/index.html'), 'rb') as f:
                return [f.read()]

        if path == '/chat' and method == 'POST':
            length = int(env.get('CONTENT_LENGTH', 0))
            body = env['wsgi.input'].read(length)
            data = json.loads(body.decode())
            prompt = data.get('prompt')
            
            # Validation de l'entrée
            if not prompt or len(prompt.strip()) < 3:
                start_response('400 Bad Request', [('Content-Type', 'application/json')])
                return [json.dumps({'error': 'Question trop courte ou vide'}).encode()]
            
            logger.info(f"Question reçue: {prompt}")
            
            # Obtenir la réponse du chatbot
            response = current_bot.respond(prompt)
            
            # Nettoyer et formater la réponse
            clean_response = sanitize_response(response)
            
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [json.dumps({'response': clean_response}).encode()]

        if path == '/switch' and method == 'POST':
            length = int(env.get('CONTENT_LENGTH', 0))
            body = env['wsgi.input'].read(length)
            data = json.loads(body.decode())
            name = data.get('bot_name')
            if name in CHATBOTS:
                current_bot = CHATBOTS[name]
                logger.info(f"Changement de bot: {name}")
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [json.dumps({'message': f'Expert changé: {name}'}).encode()]
            start_response('400 Bad Request', [('Content-Type', 'application/json')])
            return [json.dumps({'error': 'Expert non trouvé'}).encode()]

        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Page non trouvee']

    except Exception as e:
        logger.error(f"Erreur: {str(e)}")
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
        return [b'Erreur interne du serveur']

if __name__ == '__main__':
    logger.info("Serveur demarré sur http://localhost:8000")
    make_server('0.0.0.0', 8000, app).serve_forever()