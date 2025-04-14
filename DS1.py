import re
import json
import torch
import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging


logging.basicConfig(level=logging.INFO)

DOCUMENTS_JSON = "data.json"
MODEL_NAME = "deepseek-ai/deepseek-coder-7b-instruct-v1.5"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


torch.backends.cuda.enable_flash_sdp(True)
torch.backends.cuda.enable_mem_efficient_sdp(True)


class DocumentRetriever:

    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.retriever = SentenceTransformer(model_name, device='cpu')

    def get_relevant_docs(self, query, documents, top_k=3, chunk_size=1000):

        query_embedding = self.retriever.encode(query)

        chunks = []
        for doc in documents:
            text = doc['text']
            text_chunks = [
                text[i:i + chunk_size]
                for i in range(0, len(text), chunk_size)
            ]

            for i, chunk in enumerate(text_chunks[:5]):
                chunks.append({
                    'name': f"{doc['name']} (чанк {i + 1})",
                    'text': chunk,
                })

        chunk_embeddings = self.retriever.encode([c['text'] for c in chunks])

        similarities = np.dot(chunk_embeddings, query_embedding)

        top_indices = np.argsort(similarities)[-top_k:][::-1]
        best_chunks = [chunks[i] for i in top_indices]

        threshold = 0.25

        best_score = similarities[top_indices[0]]
        if best_score < threshold:
            return []


        return best_chunks

def init_llm(model_name):

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    return tokenizer, model

def generate_response(query, documents, retriever, tokenizer, model):

    relevant_docs = retriever.get_relevant_docs(query, documents)


    if not relevant_docs:
        return "Информация не найдена"


    context_parts = []
    for doc in relevant_docs:
        context_parts.append(f"Документ: {doc['name']}\n{doc['text']}")

    context = "\n\n".join(context_parts)

    prompt = (
        f"Запрос: {query}\n\n"
        f"Контекст:\n{context}\n\n"
        "Ответь кратко и по делу, используя только информацию из указанных текстов. "
        "Если ответа нет в документах, скажи 'Информация не найдена'.\n\n"
        "Ответ:"
    )


    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096).to(device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=500,
        temperature=0.7,  # креативность
        top_p=0.9,  #  разнообразие
        do_sample=True
    )
    result = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return result

def main():

    try:
        with open(DOCUMENTS_JSON, 'r', encoding='utf-8') as f:
            documents = json.load(f)
    except FileNotFoundError:
        print(f"Файл {DOCUMENTS_JSON} не найден. Запустите сначала Даник придумай имя файла.py")
        return
    except json.JSONDecodeError:
        print(f"Файл {DOCUMENTS_JSON} содержит некорректный JSON.")
        return

    retriever = DocumentRetriever()

    tokenizer, model = init_llm(MODEL_NAME)

    print("\nДобро пожаловать!)")
    print("Пишите ваш запрос. Пустая строка - завершение.")

    while True:
        user_query = input("\nВаш вопрос (Enter для выхода): ").strip()
        if not user_query:
            break

        response = generate_response(
            query=user_query,
            documents=documents,
            retriever=retriever,
            tokenizer=tokenizer,
            model=model
        )

        cleaned_response = re.sub(r'[\x00-\x1F]+', ' ', response).strip()

        print("\nОтвет:")
        print(cleaned_response[:2000])

if __name__ == "__main__":
    main()