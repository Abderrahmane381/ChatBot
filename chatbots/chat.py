# chatbots/chat.py
import os
import subprocess
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage



class ChatbotBase:
    
            
    def __init__(self, csv_folder: str, rag_template: str, embedding_model: str, llm_model: str, api_key: str):
        fichiers_csv = [f for f in os.listdir(csv_folder) if f.endswith('.csv')]
        data = []
        for f in fichiers_csv:
            loader = CSVLoader(file_path=os.path.join(csv_folder, f), encoding='utf-8')
            data += loader.load()

        # Augmenter la taille des chunks pour avoir plus de contexte
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents(data)

        ollama_path = "C:/Users/dell/AppData/Local/Programs/Ollama/ollama.exe"
        subprocess.run([ollama_path, 'pull', embedding_model], check=True)
        subprocess.run([ollama_path, 'pull', llm_model], check=True)

        embeddings = OllamaEmbeddings(model=embedding_model)
        vectorstore = InMemoryVectorStore.from_texts(
            texts=[doc.page_content for doc in chunks],
            embedding=embeddings,
            metadatas=[{"source": os.path.basename(doc.metadata.get("source", ""))} for doc in chunks]
        )
        # Récupérer plus de documents pour augmenter les chances d'avoir l'info pertinente
        base_retriever = vectorstore.as_retriever(search_kwargs={'k': 5})

        llm_compression = ChatGroq(api_key=api_key, model="meta-llama/llama-4-maverick-17b-128e-instruct")
        compressor = LLMChainExtractor.from_llm(llm_compression)
        self.retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever
        )

        self.prompt = ChatPromptTemplate.from_template(rag_template)
        # Réduire la température pour des réponses plus déterministes
        self.llm = ChatGroq(temperature=0.1, api_key=api_key, model="meta-llama/llama-4-maverick-17b-128e-instruct")
        self.memory = ConversationBufferMemory(memory_key='history', return_messages=False)

    # Dans la méthode respond de ChatbotBase, ajoutez un prétraitement pour améliorer la récupération

    def respond(self, message: str) -> str:
        # Expansion de la question pour améliorer la récupération
        expanded_query = self._expand_query(message)
    
        # Utiliser à la fois la question originale et la version étendue
        docs_original = self.retriever.get_relevant_documents(message)
        docs_expanded = self.retriever.get_relevant_documents(expanded_query)
    
        # Fusionner et dédupliquer les résultats
        all_docs = []
        doc_contents = set()
    
        for doc in docs_original + docs_expanded:
            if doc.page_content not in doc_contents:
                all_docs.append(doc)
                doc_contents.add(doc.page_content)
    
        # Limiter à un nombre raisonnable de documents
        docs = all_docs[:15]
    
        # Continuer comme avant avec le formatage du contexte...
        context_items = []
        for d in docs:
            source = d.metadata.get("source", "inconnu")
            content = d.page_content.strip()
            context_items.append(f"[Source: {source}] {content}")
    
        context = "\n\n".join(context_items)
    
        if not context.strip():
            context = "Aucune information pertinente trouvée dans la base de connaissances."

        formatted = self.prompt.format(
            history=self.memory.buffer,
            context=context,
            question=message
        )
    
        response = self.llm([HumanMessage(content=formatted)]).content
        response = self._clean_response(response)
    
        self.memory.save_context({'input': message}, {'output': response})
        return response

    def _expand_query(self, query):
        """Élargit la requête pour améliorer la récupération"""
        # Pour les servomoteurs, ajouter des termes connexes
        expanded = query
    
        # Ajouter des synonymes et termes associés aux problèmes courants
        if "servomoteur" in query.lower() or "servo" in query.lower():
            expanded += " instabilité problème contrôle PWM signal impulsion"
    
        if "aléatoire" in query.lower() or "instable" in query.lower():
            expanded += " fluctuation parasite interférence bruit signal"
    
        if "python" in query.lower():
            expanded += " communication série serial pyserial timing delay"
    
        return expanded
    
    def _clean_response(self, text):
        """Nettoie la réponse de tout élément HTML ou markdown indésirable."""
        import re
        
        # Supprimer les balises HTML complètes
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remplacer les sauts de ligne multiples par deux sauts de ligne max
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()