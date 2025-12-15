import tensorflow as tf
import numpy as np
import pdfplumber
import json
import re
import os
from sklearn.utils import shuffle
from sklearn.model_selection import train_test_split

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"


def extract_text_from_pdf(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)
    return " ".join(pages) 

def get_training_data():
    data = [
        ("glucose level 95 mg/dL", ['B-LAB', 'I-LAB', 'B-VAL', 'I-VAL', 'I-VAL']),
        ("blood pressure 120/80", ['B-VIT', 'I-VIT', 'B-VAL']),
        ("heart rate 72 bpm", ['B-VIT', 'I-VIT', 'B-VAL', 'I-VAL']),
        ("temperature 98.6 F", ['B-VIT', 'B-VAL', 'I-VAL']),
       
    ]
    return data


def build_lookup(data):
    lookup = {}
    for sentence, tags in data:
        words = sentence.lower().split()
        for w, t in zip(words, tags):
            lookup[w] = t
    return lookup


def tokenize_and_label(text, lookup):
    tokens = re.findall(r'\S+', text.lower()) 
    labeled = []
    for token in tokens:
        tag = lookup.get(token, "O")
        labeled.append({"token": token, "tag": tag})
    return labeled

def prepare_model_data(labeled_data, word_to_idx=None, tag_to_idx=None, max_len=50):
    sentences, labels = [], []

    for item in labeled_data:
        words = [item['token']]
        tags = [item['tag']]
        word_ids = [word_to_idx.get(w, word_to_idx['<UNK>']) for w in words]
        tag_ids = [tag_to_idx[t] for t in tags]

        
        pad_len = max_len - len(word_ids)
        word_ids += [0] * pad_len
        tag_ids += [-1] * pad_len

        sentences.append(word_ids[:max_len])
        labels.append(tag_ids[:max_len])

    return np.array(sentences), np.array(labels)


def build_ner_model(vocab_size, num_tags, max_len=50):
    model = tf.keras.Sequential([
        tf.keras.layers.Embedding(vocab_size, 128, mask_zero=True),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(64, return_sequences=True, dropout=0.2)),
        tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(32, return_sequences=True, dropout=0.2)),
        tf.keras.layers.Dense(num_tags, activation='softmax')
    ])
    model.build(input_shape=(None,128))
    model.summary()
    model.compile(
        optimizer='adam',
        loss=tf.keras.losses.SparseCategoricalCrossentropy(ignore_class=-1),
        metrics=['accuracy']
    )
    return model


def main(pdf_path="AI_11_ISC_2.pdf"):
  
    pdf_text = extract_text_from_pdf(pdf_path)

   
    training_data = get_training_data()
    lookup = build_lookup(training_data)

 
    pdf_labeled = tokenize_and_label(pdf_text, lookup)

    
    with open("output.json", "w") as f:
        json.dump(pdf_labeled, f, indent=2)
    print("✅ PDF tokens saved to output.json")

   
    all_words = set()
    all_tags = set()
    for sent, tags in training_data:
        for w in sent.lower().split():
            all_words.add(w)
        for t in tags:
            all_tags.add(t)

    word_to_idx = {w: i+2 for i, w in enumerate(sorted(all_words))}
    word_to_idx['<PAD>'] = 0
    word_to_idx['<UNK>'] = 1

    tag_to_idx = {t: i for i, t in enumerate(sorted(all_tags))}
    tag_to_idx['O'] = len(tag_to_idx) 

    
    train_sentences = []
    for sent, tags in training_data:
        for w, t in zip(sent.lower().split(), tags):
            train_sentences.append({'token': w, 'tag': t})

   
    train_sentences = shuffle(train_sentences, random_state=42)

    X_train, y_train = prepare_model_data(train_sentences, word_to_idx, tag_to_idx)

   
    model = build_ner_model(vocab_size=len(word_to_idx), num_tags=len(tag_to_idx))
    model.fit(X_train, y_train, epochs=30, batch_size=32, validation_split=0.2)

   
    pdf_tokens = [d['token'] for d in pdf_labeled]
    ids = [word_to_idx.get(w, word_to_idx['<UNK>']) for w in pdf_tokens]
    ids += [0] * (50 - len(ids))
    preds = model.predict(np.array([ids]), verbose=0)
    pred_tags = [list(tag_to_idx.keys())[np.argmax(p)] for p in preds[0][:len(pdf_tokens)]]

    
    print("NER Prediction (first 20 tokens):", list(zip(pdf_tokens[:20], pred_tags[:20])))

if __name__ == "__main__":
    main("AI_11_ISC_2.pdf")
