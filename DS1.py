import re
import json
import torch
import numpy as np
import nltk
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM, StoppingCriteria, StoppingCriteriaList
import logging
from nltk.tokenize import sent_tokenize

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')

logging.basicConfig(level=logging.INFO)

DOCUMENTS_JSON = "output/data.json"
MODEL_NAME = "deepseek-ai/deepseek-coder-7b-instruct-v1.5"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class StopOnTokens(StoppingCriteria):
    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        stop_ids = [0]
        return input_ids[0][-1] in stop_ids


def split_into_chunks(text, chunk_size=300):
    try:
        sentences = sent_tokenize(text)

    except:
        sentences = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    chunks = []
    current_chunk = []
    current_length = 0

    for sent in sentences:
        if current_length + len(sent) > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_length = 0

        current_chunk.append(sent)
        current_length += len(sent)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


class DocumentRetriever:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.retriever = SentenceTransformer(model_name, device='cpu')

    def get_relevant_docs(self, query, documents, top_k=3):
        try:
            query_embedding = self.retriever.encode(query)
            chunks = []

            for doc in documents:
                text = str(doc.get('text', ''))  # Защита от дырок
                text_chunks = split_into_chunks(text)

                for i, chunk in enumerate(text_chunks[:5]):
                    chunks.append({
                        'name': f"{doc.get('name', 'Без названия')} (чанк {i + 1})",
                        'text': chunk,
                    })

            if not chunks:
                return []

            chunk_embeddings = self.retriever.encode([c['text'] for c in chunks])
            similarities = np.dot(chunk_embeddings, query_embedding)
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            best_chunks = [chunks[i] for i in top_indices]

            return best_chunks if similarities[top_indices[0]] >= 0.25 else []

        except Exception as e:
            logging.error(f"Ошибка при поиске документов: {e}")
            return []


def init_llm(model_name):
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="left"
        )

        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float16, # потом поменять на 32
            device_map="auto"
        )
        return tokenizer, model

    except Exception as e:
        logging.error(f"Ошибка при загрузке модели: {e}")
        raise


def generate_response(query, documents, retriever, tokenizer, model):
    try:
        relevant_docs = retriever.get_relevant_docs(query, documents)

        if not relevant_docs:
            return "Информация не найдена"

        context = format_context(relevant_docs)

        prompt = f"""
        [ИНСТРУКЦИИ]
        1. Ответь ТОЛЬКО на основе приведенного контекста
        2. Используй понятные примеры из реальной жизни
        3. Избегай технических терминов
        4. Форматируй ответ как маркированный список

        [КОНТЕКСТ]
        {context}

        [ВОПРОС]
        {query}

        [ОТВЕТ]
        """

        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096).to(device)

        outputs = model.generate(
            **inputs,
            max_new_tokens=400,
            temperature=0.3,
            top_p=0.85,
            repetition_penalty=1.2,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
            stopping_criteria=StoppingCriteriaList([StopOnTokens()])
        )

        result = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return clean_response(result, query)
    except Exception as e:
        logging.error(f"Ошибка при генерации ответа: {e}")
        return "Произошла ошибка при обработке запроса"


def format_context(chunks):
    cleaned = []
    for chunk in chunks:
        text = re.sub(r'\.\.\.\d+\.\.\.', '', chunk.get('text', ''))
        text = re.sub(r'\[\d+\.\d+\.\d+\]', '', text)
        cleaned.append(f"📄 {chunk.get('name', 'Без названия')}:\n{text}")
    return "\n\n".join(cleaned)


def clean_response(response, query):
    try:
        if '<|im_start|>assistant' in response:
            response = response.split('<|im_start|>assistant')[-1].strip()

        response = re.sub(r'\[\d+\.\d+\.\d+\]', '', response)

        sentences = sent_tokenize(response)
        return ' '.join(sentences[:10])  # Ограничиваем 10 предложениями (пока что) мб сделать 2 версии
    except:
        return response[:1000]


def main():
    try:
        with open(DOCUMENTS_JSON, 'r', encoding='utf-8') as f:
            documents = json.load(f)
    except FileNotFoundError:
        print(f"Файл {DOCUMENTS_JSON} не найден.")
        return
    except json.JSONDecodeError:
        print(f"Ошибка в формате файла {DOCUMENTS_JSON}.")
        return
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return

    try:
        retriever = DocumentRetriever()
        tokenizer, model = init_llm(MODEL_NAME)
    except Exception as e:
        print(f"Ошибка инициализации: {e}")
        return

    print("\nДобро пожаловать!")
    print("Введите ваш вопрос. Для выхода нажмите Enter.")

    while True:
        try:
            user_query = input("\nВаш вопрос: ").strip()
            if not user_query:
                break

            response = generate_response(
                query=user_query,
                documents=documents,
                retriever=retriever,
                tokenizer=tokenizer,
                model=model
            )

            print("\nОтвет:")
            print(response[:2000])
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Ошибка обработки запроса: {e}")


if __name__ == "__main__":
    main()