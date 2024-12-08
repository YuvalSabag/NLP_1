import math
from collections import defaultdict, Counter
import re
import string
import random

import spelling_confusion_matrices

class Spell_Checker:
    """The class implements a context-sensitive spell checker. The corrections
        are done in the Noisy Channel framework, based on a language model and
        an error distribution model.
    """

    def __init__(self, lm=None):
        """Initializing a spell checker object with a language model as an
        instance variable.

        Args:
            lm: a language model object. Defaults to None.
        """
        self.lm = lm
        self.error_tables = None  # a dictionary of error tables in the format of the provided confusion matrices.

    def add_language_model(self, lm):
        """Adds the specified language model as an instance variable.
            (Replaces an older LM dictionary if set)

            Args:
                lm: a Spell_Checker.Language_Model object
        """
        self.lm = lm

    def add_error_tables(self, error_tables):
        """ Adds the specified dictionary of error tables as an instance variable.
            (Replaces an older value dictionary if set)

            Args:
            error_tables (dict): a dictionary of error tables in the format
            of the provided confusion matrices:
            https://www.dropbox.com/s/ic40soda29emt4a/spelling_confusion_matrices.py?dl=0
        """
        self.error_tables = error_tables

    def evaluate_text(self, text):
        """Returns the log-likelihood of the specified text given the language
            model in use. Smoothing should be applied on texts containing OOV words
    
           Args:
               text (str): Text to evaluate.
    
           Returns:
               Float. The float should reflect the (log) probability.
        """
        if not self.lm:
            raise ValueError("No language model was set.")
        else:
            return self.lm.evaluate_text(text)

    def known(self, words):
        """ the filter of the words that are known to the language model.
            Args:
                words : sentence to filter
            Returns:
                A set of the words that are known to the language model.
        """
        # Filter words known to the language model
        known_words = set(word for word in words if word in self.lm.get_vocab())
        return known_words

    @staticmethod
    def edits1(word):
        """All edits that are one edit away from `word`."""
        letters = 'abcdefghijklmnopqrstuvwxyz'
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        inserts = [L + c + R for L, R in splits for c in letters]
        return set(deletes + transposes + replaces + inserts)

    def edits2(self, word):
        """All edits that are two edits away from `word`."""
        return (e2 for e1 in self.edits1(word) for e2 in self.edits1(e1))

    def get_candidates(self, word):
        """Returns a set of candidate words for the specified word.
            The candidates are generated by applying the edits1 and edits2 functions
            on the specified word.

            Args:
                word (str): the word to generate candidates for.

            Returns:
                A set of candidate words.
        """
        return self.known([word]) or self.known(self.edits1(word)) or self.known(self.edits2(word)) or {word}

    def get_correction(self, word, context, alpha):
        """
        Returns the most probable correction for the specified word given the context.
        The probability of keeping the word as is (no correction) is given by the alpha parameter.

        Args:
            word (str): the word to correct.
            context (str): the context of the word.
            alpha (float): the probability of keeping the word as is.

        Returns:
            A string. The most probable correction for the specified word.
        """
        candidates = self.get_candidates(word)
        if not candidates:
            return word

        # Find the best candidate by evaluating combined probabilities
        best_candidate = max(candidates,
                             key=lambda candidate: self.compute_candidate_probability(candidate, word, context, alpha))
        return best_candidate

    def compute_candidate_probability(self, candidate, original_word, context, alpha):
        """
        Most probable spelling correction for word

        Computes the probability of a candidate given the original word and its context.

        Args:
            candidate (str): The corrected word.
            original_word (str): The original word.
            context (str): The context in which the word appears (n-1 prior words).
            alpha (float): The probability of keeping a lexical word as is.

        Returns:
            float: The combined probability of the candidate.
        """
        # Concatenate context with corrected word
        full_context = f"{context} {candidate}"

        log_likelihood = self.lm.evaluate_text(full_context)  # Evaluate the context with the corrected word
        language_model_probability = math.exp(log_likelihood)
        error_model_probability = self.compute_error_prob(candidate, original_word, alpha)

        combine_probabilities = language_model_probability * error_model_probability  # (lm prob and error prob)

        return 1e-8 * combine_probabilities

    def compute_error_prob(self, candidate, original_word, alpha):
        """
        Calculate the probability of transforming the original word to the candidate.
        It utilizes both direct edit probability and distance 2 probability through an intermediate word.

        Args:
            candidate (str): The candidate word.
            original_word (str): The original word.
            alpha (float): The probability of keeping the word as is.

        Returns:
            float: The probability of transforming the original word to the candidate.
        """
        # Get the direct edit probability
        direct_prob = self.get_first_edit_probability(candidate, original_word, alpha)

        # Get the distance 2 probability
        distance_2_prob = self.calculate_distance_2_probability(candidate, original_word, alpha)

        # Return the maximum of the direct and distance 2 probabilities
        return max(direct_prob, distance_2_prob)

    def get_first_edit_probability(self, candidate, original_word, alpha):
        """
        Calculate the probability of transforming `original_word` to `candidate` directly using edit operations.
        The function returns the maximum probability of the following operations:
        insertion, deletion, substitution, transposition, and keeping the word as is.

        If the word is unchanged, the probability of keeping it as is (`alpha`) is returned.

        Args:
            candidate (str): The candidate word.
            original_word (str): The original word.
            alpha (float): The probability of keeping the word as is.

        Returns:
            float: The probability of transforming the original word to the candidate directly.
        """
        if not self.error_tables or original_word == candidate:
            return alpha

        prob_insert = 0.0
        if len(candidate) == len(original_word) - 1:
            prob_insert = self.insertion_probability(candidate, original_word)

        prob_delete = 0.0
        if len(candidate) == len(original_word) + 1:
            prob_delete = self.deletion_probability(candidate, original_word)

        prob_subst = 0.0
        prob_trans = 0.0
        if len(candidate) == len(original_word):
            prob_subst = self.substitution_probability(candidate, original_word)
            prob_trans = self.transposition_probability(candidate, original_word)

        return max(prob_insert, prob_delete, prob_subst, prob_trans, 1e-8)

    def calculate_distance_2_probability(self, candidate, original_word, alpha):
        """
        Calculate the probability of transforming the original word to the candidate
        through an intermediate word using the error tables. The function returns the
        maximum probability of the following operations: insertion, deletion,
        substitution, transposition, and keeping the word as is.

        Args:
            candidate (str): The candidate word.
            original_word (str): The original word.
            alpha (float): The probability of keeping the word as is.

        Returns:
            float: The probability of transforming the original word to the candidate
                   through an intermediate word.
        """
        # Initialize with the direct edit probability
        max_probability = self.get_first_edit_probability(candidate, original_word, alpha)

        # Generate all intermediate words and their respective next edits in one go
        intermediate_words = [(intermediate, next_edit)
                              for intermediate in self.edits1(original_word)  # Generate all edits of the original word
                              for next_edit in self.edits1(intermediate)  # Generate all edits of the intermediate word
                              if next_edit == candidate]  # Filter out the candidate words

        # Iterate through the generated intermediate words and next edits
        for intermediate, next_edit in intermediate_words:
            probability_intermediate_to_original = self.get_first_edit_probability(intermediate, original_word, alpha)
            probability_candidate_to_intermediate = self.get_first_edit_probability(candidate, intermediate, alpha)
            combined_probability = probability_intermediate_to_original * probability_candidate_to_intermediate
            max_probability = max(max_probability, combined_probability)

        return max_probability

    def deletion_probability(self, modified_word, original_word):
        """
        Calculate the probability of a deletion error that transforms 'original_word' into 'modified_word'.
        It identifies where the deletion has likely occurred and computes the probability using an error table.

        Args:
            modified_word (str): The word after the deletion error.
            original_word (str): The original word before the deletion error.

        Returns:
            float: The probability of the deletion error.
        """
        if len(modified_word) != len(original_word) + 1:
            return 0.0

        for idx, char in enumerate(modified_word):
            # Simulate adding one character to modified_word at position index
            if modified_word[:idx] + modified_word[idx + 1:] == original_word:
                # Character deleted is modified_word[idx], after character modified_word[idx] or at the end
                if idx == 0:
                    char_pair = '#' + char  # '#' represents the start of the word
                else:
                    char_pair = modified_word[idx - 1] + char

                deletion_prob = self.error_tables['deletion'].get(char_pair, 0.0)
                char_pair_frequency = self.lm.char_pair.get(char_pair, 0.0)
                return deletion_prob / char_pair_frequency if char_pair_frequency else 0.0

        return 0.0  # if no deletion point is found

    def insertion_probability(self, modified_word, original_word):
        """
        Calculate the probability of an insertion error that transforms 'original_word' into 'modified_word'.
        It identifies where the insertion has likely occurred and computes the probability using an error table.

        Args:
            modified_word (str): The word after the insertion error.
            original_word (str): The original word before the insertion error.

        Returns:
            float: The probability of the insertion error.
        """
        if len(modified_word) != len(original_word) - 1:
            return 0.0

        for idx, char in enumerate(original_word):
            # Simulate removing one character from original_word at position index
            if original_word[:idx] + original_word[idx + 1:] == modified_word:
                # Character inserted is modified_word[idx], after character original_word[idx] or at the end
                if idx == 0:
                    char_pair = '#' + char
                else:
                    char_pair = original_word[idx - 1] + char

                insertion_prob = self.error_tables['insertion'].get(char_pair, 0.0)
                char_frequency = self.lm.char_counts.get(char_pair[0], 0.0)
                return insertion_prob / char_frequency if char_frequency else 0.0

        return 0.0  # if no insertion point is found

    def substitution_probability(self, modified_word, original_word):
        """
        Calculate the probability of a substitution error that transforms 'original_word' into 'modified_word'.
        It identifies where the substitution has likely occurred and computes the probability using an error table.

        Args:
            modified_word (str): The word after the substitution error.
            original_word (str): The original word before the substitution error.

        Returns:
            float: The probability of the substitution error.
        """
        if len(modified_word) != len(original_word):
            return 0.0

        for mod_char, orig_char in zip(modified_word, original_word):
            if mod_char != orig_char:
                char_pair = orig_char + mod_char
                substitution_prob = self.error_tables['substitution'].get(char_pair, 0.0)
                orig_char_frequency = self.lm.char_counts.get(char_pair[1], 0.0)
                return substitution_prob / orig_char_frequency if orig_char_frequency else 0.0

        return 0.0  # if no substitution point is found

    def transposition_probability(self, modified_word, original_word):
        """
        Calculate the probability of a transposition error that transforms 'original_word' into 'modified_word'.
        It identifies where the transposition has likely occurred and computes the probability using an error table.

        Args:
            modified_word (str): The word after the transposition error.
            original_word (str): The original word before the transposition error.

        Returns:
            float: The probability of the transposition error.
        """
        if len(modified_word) != len(original_word):
            return 0.0

        for i in range(len(original_word) - 1):
            if (original_word[i] == modified_word[i + 1] and
                    original_word[i + 1] == modified_word[i] and
                    original_word[:i] + original_word[i + 2:] == modified_word[:i] + modified_word[i + 2:]):
                char_pair = original_word[i:i + 2]  # Pair of characters to be transposed
                transposition_prob = self.error_tables['transposition'].get(char_pair, 0.0)
                char_pair_frequency = self.lm.char_pair.get(char_pair, 0.0)
                return transposition_prob / char_pair_frequency if char_pair_frequency else 0.0

        return 1e-8  # if no transposition point is found

    def spell_check(self, text, alpha):
        """ Returns the most probable fix for the specified text. Use a simple
            noisy channel model if the number of tokens in the specified text is
            smaller than the length (n) of the language model.

            Args:
                text (str): the text to spell check.
                alpha (float): the probability of keeping a lexical word as is.

            Return:
                A modified string (or a copy of the original if no corrections are made.)
        """
        text = normalize_text(text)
        tokens = text.split()

        # If the text is empty after normalization, return it as is
        if not tokens:
            return text

        # Initialize the list for corrected words
        corrected_words = []

        # Get the n-gram window size
        n = self.lm.get_model_window_size()

        # If the text is shorter than the n-gram window size, use a simple correction model
        if len(tokens) < n:
            for token in tokens:
                if token in self.lm.get_vocab():
                    corrected_words.append(token)
                else:
                    corrected_word = self.get_correction(token, '', alpha)
                    corrected_words.append(corrected_word)
            return ' '.join(corrected_words)

        # Handle OOV words and spelling mistakes
        oov_indices = [i for i, token in enumerate(tokens) if token not in self.lm.get_vocab()]
        if oov_indices:
            for i in oov_indices:
                context_start = max(0, i - n + 1)
                context = ' '.join(tokens[context_start:i])
                corrected_word = self.get_correction(tokens[i], context, alpha)
                if corrected_word != tokens[i]:
                    tokens[i] = corrected_word
                    return ' '.join(tokens)

        # Generate possible corrected sentences for spelling mistakes
        possible_sentences = []
        original_sentence = ' '.join(tokens)
        possible_sentences.append(original_sentence)

        for i, token in enumerate(tokens):
            candidates = self.get_candidates(token)
            for candidate in candidates:
                if candidate != token:
                    new_sentence = tokens[:i] + [candidate] + tokens[i + 1:]
                    possible_sentences.append(' '.join(new_sentence))

        # Score the possible sentences
        def score_sentence(sentence, original_sentence, log_likelihood, alpha):
            """Calculate the probability of a sentence."""
            if sentence == original_sentence:
                return math.exp(log_likelihood) * alpha
            else:
                return math.exp(log_likelihood) * (1 - alpha)

        scored_sentences = []
        for sentence in possible_sentences:
            log_likelihood = self.evaluate_text(sentence)
            probability = score_sentence(sentence, original_sentence, log_likelihood, alpha)
            scored_sentences.append((probability, sentence))

        # Return the sentence with the highest probability
        best_sentence = max(scored_sentences, key=lambda x: x[0])[1]
        return best_sentence

    #####################################################################
    #                   Inner class                                     #
    #####################################################################

    class Language_Model:
        """The class implements a Markov Language Model that learns a model from a given text.
            It supports language generation and the evaluation of a given string.
            The class can be applied on both word level and character level.
        """

        def __init__(self, n=3, chars=False):
            """Initializing a language model object.
            Args:
                n (int): the length of the markov unit (the n of the n-gram). Defaults to 3.
                chars (bool): True iff the model consists of ngrams of characters rather than word tokens.
                              Defaults to False
            """
            self.n = n
            self.chars = chars  # True if the model is character based, False if it is word based.
            self.char_pair = Counter()  # a dictionary of the form {'char1, char2':count}
            self.char_counts = Counter()  # a dictionary of the form {char:count}
            self.model_dict = defaultdict(int)  # a dictionary of the form {ngram:count}, holding counts of all
            # ngrams in the specified text.
            self.suggestions = defaultdict(Counter)  # a dict of the form {ngram-1: {next_word: count}}, holding counts
            # of all suggestions for each ngram.
            self.freq_tokens = Counter()   # a dictionary of the form {token:count}, holding counts of all tokens in the
            self.token_count = 0  # the total number of tokens in the text.
            self.vocab = set()  # a set of all tokens in the text.

            # NOTE: This dictionary format is inefficient and insufficient (why?),
            # therefore  you can (even encouraged to) use a better data structure. However, you are requested to
            # support this format for two reasons: (1) It is very straight forward and force you to understand the
            # logic behind LM, and (2) It serves as the normal form for the LM, so we can call get_model_dictionary()
            # and peek into you model.

        def build_model(self, text):
            """populates the instance variable model_dict.

                Args:
                    text (str): the text to construct the model from.
            """
            normalized_text = normalize_text(text)

            if self.chars:
                tokens = list(normalized_text)
            else:
                tokens = normalized_text.split()

            # Count single pairs of letters frequency (for errors probability)
            for i in range(len(normalized_text) - 1):
                self.char_counts[normalized_text[i]] += 1
                char_pair = normalized_text[i:i + 2]
                self.char_pair[char_pair] += 1
            self.char_counts[normalized_text[-1]] += 1

            # for token in tokens:
            #     self.freq_tokens[token] += 1  # count the frequency of each token
            self.freq_tokens.update(tokens)
            self.token_count = sum(self.freq_tokens.values())  # count the total number of tokens
            self.vocab.update(self.freq_tokens.keys())  # set of all tokens in the text

            tokens = ['<s>'] * (self.n - 1) + tokens + ['</s>']  # add start and end tokens

            for i in range(self.n - 1, len(tokens)):
                ngram = tuple(tokens[i - self.n + 1:i + 1])  # create the ngram
                next_token = tokens[i]
                self.model_dict[ngram] += 1
                # self.suggestions[ngram[:-1]][next_token] = self.suggestions[ngram[:-1]].get(next_token, 0) + 1
                self.suggestions[ngram[:-1]][next_token] += 1

        def get_char_pair(self):
            """Returns the char_pair dictionary
            """
            return self.char_pair

        def get_char_counts(self):
            """Returns the char_counts dictionary
            """
            return self.char_counts

        def get_token_count(self):
            """Returns the total number of tokens in the text.
            """
            return self.token_count

        def get_vocab(self):
            """Returns the set of all tokens in the text.
            """
            return self.vocab

        def get_freq_tokens(self):
            """Returns a dictionary of the form {token:count}, holding counts of all tokens in the specified text.
            """
            return self.freq_tokens

        def get_suggestions(self):
            """Returns a dictionary of the form {ngram-1:Counter}, holding counts of all suggestions for each ngram.
            """
            return self.suggestions

        def get_model_dictionary(self):
            """Returns the dictionary class object
            """
            return self.model_dict

        def get_model_window_size(self):
            """Returning the size of the context window (the n in "n-gram")
            """
            return self.n

        def _get_next_token(self, context_prefix):
            """Returns the next token given the specified context prefix."""
            if context_prefix in self.suggestions:
                suggestions = self.suggestions[context_prefix]
                total_count = sum(suggestions.values())
                rand_value = random.randint(1, total_count)
                cumulative_count = 0
                for token, count in suggestions.items():
                    cumulative_count += count
                    if cumulative_count >= rand_value:
                        return token
            return None

        def generate(self, context=None, n=20):
            """Returns a string of the specified length, generated by applying the language model
            to the specified seed context. If no context is specified the context should be sampled
            from the models' contexts distribution. Generation should stop before the n'th word if the
            contexts are exhausted. If the length of the specified context exceeds (or equal to)
            the specified n, the method should return a prefix of length n of the specified context.

                Args:
                    context (str): a seed context to start the generated string from. Defaults to None
                    n (int): the length of the string to be generated.

                Return:
                    String. The generated text.

            """

            generated_text = []

            if context is None:
                # If no context is provided, sample a context from suggestions
                context_tokens = random.choice(list(self.suggestions.keys()))
            else:
                normalized_context = normalize_text(context)  # Normalize the context
                if self.chars:
                    context_tokens = list(normalized_context)
                else:
                    context_tokens = normalized_context.split()

                # If the length of the provided context equals or exceeds n, return the prefix of length n
                if len(context_tokens) >= n:
                    if self.chars:
                        return ''.join(context_tokens[:n])
                    else:
                        return ' '.join(context_tokens[:n])

            generated_text.extend(context_tokens)  # add the context to the generated text

            while len(generated_text) < n:
                context_prefix = tuple(generated_text[-(self.n - 1):])
                next_token = self._get_next_token(context_prefix)
                if next_token is None:
                    break
                generated_text.append(next_token)

            # Remove '<s>' and '</s>' tokens from the generated text
            generated_text = [token for token in generated_text if token not in ['<s>', '</s>']]

            if self.chars:
                return ''.join(generated_text)
            else:
                return ' '.join(generated_text)

        def evaluate_text(self, text):
            """Returns the log-likelihood of the specified text to be a product of the model.
               Laplace smoothing should be applied if necessary.

               Args:
                   text (str): Text to evaluate.

               Returns:
                   Float. The float should reflect the (log) probability.
            """

            normalized_text = normalize_text(text)

            if self.chars:
                tokens = list(normalized_text)
            else:
                tokens = normalized_text.split()

            # Check if there are no tokens after normalization
            if not tokens:
                return float('-inf')

            # Check for out-of-vocabulary (OOV) words for this n-gram
            smooth = any(token not in self.freq_tokens for token in tokens)

            # Add start and end tokens based on the n-gram window size
            window_size = self.get_model_window_size()
            tokens = ['<s>'] * (window_size - 1) + tokens + ['</s>']

            log_prob = 0.0

            # Iterate over each n-gram in the text
            for i in range(len(tokens) - window_size + 1):
                ngram = tuple(tokens[i:i + window_size])

                if not smooth:
                    context = ngram[:-1]
                    token = ngram[-1]
                    context_count = sum(self.suggestions[context].values())
                    token_count = self.suggestions[context].get(token, 0)
                    prob = token_count / context_count if context_count > 0 else 0
                # Calculate the probability of the n-gram, applying smoothing if necessary
                else:
                    prob = self.smooth(ngram)

                # Accumulate log probabilities
                if prob > 0:
                    log_prob += math.log(prob)
                else:
                    log_prob += math.log(1e-8)  # Apply a small probability for unseen n-grams

            return log_prob


        def smooth(self, ngram):
            """Returns the smoothed (Laplace) probability of the specified ngram.

                Args:
                    ngram (str): the ngram to have its probability smoothed

                Returns:
                    float. The smoothed probability.
            """
            context, token = ngram[:-1], ngram[-1]
            context_count = sum(self.suggestions[context].values())  # Count of all tokens that follow the context
            # todo: check if token_count = self.suggestions[context].get(token, 0)
            token_count = self.model_dict.get(ngram, 0)  # Count of the specified token following the context

            # Apply Laplace smoothing
            smoothed_probability = (token_count + 1) / (context_count + len(self.get_vocab()))

            return smoothed_probability


def normalize_text(text, to_lowercase=True, remove_punctuation=True, remove_numbers=True, remove_urls=True,
                   remove_stopwords=False, stopwords=None):
    """
    Returns a normalized version of the specified string.

    This function normalizes text by performing several optional preprocessing steps:
    - Converting text to lowercase
    - Removing punctuation
    - Removing numbers
    - Removing URLs
    - Removing stopwords (if provided)

    Args:
        text (str): The text to normalize.
        to_lowercase (bool): Whether to convert text to lowercase. Defaults to True.
        remove_punctuation (bool): Whether to remove punctuation. Defaults to True.
        remove_numbers (bool): Whether to remove numbers. Defaults to True.
        remove_urls (bool): Whether to remove URLs. Defaults to True.
        remove_stopwords (bool): Whether to remove stopwords. Defaults to False.
        stopwords (set): A set of stopwords to remove from the text. Only used if remove_stopwords is True.

    Returns:
        str: The normalized text.
    """
    if to_lowercase:
        text = text.lower()

    if remove_urls:
        text = re.sub(r'https?://\S+', '', text)

    if remove_punctuation:
        text = text.translate(str.maketrans('', '', string.punctuation))

    if remove_numbers:
        text = re.sub(r'\d+', '', text)

    # Tokenize and optionally remove stopwords
    tokens = re.findall(r'\w+', text)
    if remove_stopwords and stopwords:
        tokens = [word for word in tokens if word not in stopwords]

    # Rejoin tokens into a string
    return ' '.join(tokens)





