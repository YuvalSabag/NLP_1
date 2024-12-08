##  **Probabilistic Spell Checker Using the Noisy Channel Model**

This project implements a **probabilistic spell checker** using the **Noisy Channel Model**, which combines a **language model** and an **error model** to correct spelling mistakes while considering the surrounding context. Leveraging a Markovian language model with **n-grams** to model language structure, the system evaluates the probabilities of word sequences and determines the most likely corrections in context.

This task highlights core NLP concepts, including **language modeling**, **n-gram probability computation**, **error detection**, and **context-aware corrections**, providing a comprehensive introduction to text normalization and preprocessing in NLP.


### **Key Objectives**

#### **1. Language Modeling**  
- Develop a **Markovian n-gram language model** (bigrams and trigrams) to estimate word sequence likelihoods.  
- Apply **smoothing techniques** to handle unseen n-grams and improve model accuracy.  

#### **2. Error Modeling**  
- Build an **error model** using confusion matrices to simulate common spelling errors, including:  
  - **Insertions**  
  - **Deletions**  
  - **Substitutions**  
  - **Transpositions**  

#### **3. Noisy Channel Framework**  
- Combine the language and error models in a **Noisy Channel framework**.  
- Identify and rank candidate corrections based on contextual probabilities and error likelihoods.  

#### **4. Spell Checker Implementation**  
- Design a modular and flexible **spell checker API** to:  
  - Correct both **non-word** and **real-word errors**.  
  - Handle multiple errors per word and process single erroneous words per sentence.  
