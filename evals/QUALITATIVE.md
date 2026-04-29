# Qualitative Comparison — attention.pdf at level 5
This file shows the actual output text from each model for one fixed case, to complement the quantitative rubric scores in `FINDINGS.md`. Reading the outputs side-by-side surfaces stylistic and structural differences that aggregate scores cannot capture.

**Paper:** `attention.pdf`  
**Reader level:** 5/10

---

## Rubric scores at a glance

| Model | Faith | Level | Cover | Clarity | Total | Tokens (out) |
|---|---|---|---|---|---|---|
| `gpt-5-chat` | 5 | 5 | 5 | 5 | 20/20 | 620 |
| `Llama-4-Maverick-17B-128E-Instruct-FP8` | 5 | 3 | 5 | 5 | 18/20 | 473 |
| `mistral-Large-3` | 5 | 5 | 5 | 5 | 20/20 | 1200 |

---

## Model outputs

### `gpt-5-chat`

```text
This paper introduces the Transformer, a new architecture for sequence transduction tasks such as machine translation. Unlike earlier models that rely on recurrence (RNNs, LSTMs, GRUs) or convolution, the Transformer uses only attention mechanisms to model dependencies between sequence elements. This design removes the sequential computation bottleneck of recurrent models, allowing much greater parallelism and faster training.

Traditional recurrent models process input tokens one at a time. At each step t, the model updates a hidden state h_t = f(h_{t−1}, x_t), where x_t is the input at position t. Because each h_t depends on h_{t−1}, the computation must proceed sequentially, limiting parallelization. The Transformer replaces this recurrence with self-attention, which directly relates every position in the sequence to every other position in a single operation.

The core operation is scaled dot-product attention. Given a set of queries Q, keys K, and values V, attention is computed as:

Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V

Here, d_k is the dimensionality of the keys, and the division by sqrt(d_k) stabilizes gradients by controlling the magnitude of the dot products. The softmax produces attention weights that determine how much each value contributes to the output. Intuitively, each position in the sequence attends to all others, weighting them by similarity between query and key vectors.

To allow the model to represent multiple types of relationships simultaneously, the Transformer uses multi-head attention. The input is projected into multiple lower-dimensional subspaces, each with its own Q, K, and V matrices. Attention is computed in parallel for each head, and the results are concatenated and linearly transformed. This gives the model richer representational capacity, as each head can capture different patterns of dependency.

Because the model has no recurrence or convolution, it lacks an inherent notion of order. To encode sequence position, the Transformer adds positional encodings to the input embeddings. These encodings are deterministic vectors that vary smoothly with position, allowing the model to infer relative and absolute positions.

The overall architecture follows the encoder-decoder structure common in translation. The encoder consists of multiple identical layers, each containing a multi-head self-attention sublayer and a feed-forward sublayer. The decoder also stacks similar layers but adds a third sublayer for attention over the encoder outputs, enabling the decoder to focus on relevant parts of the input sequence when generating each output token.

In experiments on large translation benchmarks, the Transformer achieved state-of-the-art results. On English-to-German translation it reached 28.4 BLEU, more than 2 BLEU higher than previous best models, and on English-to-French it achieved 41.8 BLEU with far less training time. The model also generalized well to other tasks such as constituency parsing, showing its flexibility.

In summary, the Transformer demonstrates that attention mechanisms alone are sufficient for powerful sequence modeling. By removing recurrence and convolution, it achieves both higher quality and much greater computational efficiency.
```

**Judge notes:**
- *faithfulness* (5/5): All claims and numbers are directly supported by the paper excerpt, with no invented facts.
- *level_match* (5/5): The explanation uses technical vocabulary, explains mechanisms, defines key equation symbols, and covers assumptions and main results as required for level 5.
- *coverage* (5/5): All expected topics (transformer, attention, self-attention, encoder, decoder, multi-head-attention, positional-encoding) are meaningfully addressed.
- *clarity* (5/5): The explanation has a logical flow, no confusing jumps, and is coherent from introduction to conclusion.

---

### `Llama-4-Maverick-17B-128E-Instruct-FP8`

```text
The Transformer is a new network architecture designed for sequence transduction tasks, such as machine translation. Traditional models for these tasks rely on recurrent or convolutional neural networks, often with an encoder-decoder structure and an attention mechanism. The Transformer simplifies this by abandoning recurrence and convolutions entirely, relying solely on attention mechanisms.

In traditional recurrent models, computation is typically performed sequentially along the input and output sequences. This means that the model generates a sequence of hidden states, where each state depends on the previous state and the current input. The Transformer avoids this sequential computation by using self-attention, allowing it to process input sequences in parallel.

The Transformer consists of an encoder and a decoder. The encoder takes in a sequence of symbols and outputs a sequence of vectors. The decoder then generates the output sequence, one symbol at a time, based on the output vectors from the encoder. The key innovation is the use of self-attention in both the encoder and decoder. 

Self-attention allows the model to attend to different parts of the input sequence simultaneously and weigh their importance. This is different from traditional attention mechanisms, which typically attend to the output of the encoder. The Transformer uses a specific type of self-attention called scaled dot-product attention.

The Transformer also uses a technique called multi-head attention. This involves performing multiple attention operations in parallel, with different weight matrices, and then combining the results. This allows the model to capture different types of relationships between the input elements.

To preserve the order of the input sequence, the Transformer uses positional encoding. This involves adding a vector to each input element, based on its position in the sequence. The vector is designed to allow the model to determine the position of each element.

The authors tested the Transformer on two machine translation tasks and found that it outperformed existing models, achieving a BLEU score of 28.4 on the WMT 2014 English-to-German translation task and 41.8 on the WMT 2014 English-to-French translation task. The model was also more parallelizable and required significantly less training time, taking only 3.5 days to train on eight GPUs.

The Transformer generalized well to other tasks, such as English constituency parsing, with both large and limited training data. This suggests that the Transformer is a versatile and effective architecture for a range of sequence transduction tasks.
```

**Judge notes:**
- *faithfulness* (5/5): All claims and numbers are directly supported by the paper excerpt.
- *level_match* (3/5): It uses technical vocabulary and explains mechanisms but lacks key equations and detailed assumptions.
- *coverage* (5/5): All expected topics are meaningfully addressed.
- *clarity* (5/5): The explanation has a logical flow and is coherent end-to-end.

---

### `mistral-Large-3`

```text
The Transformer is a neural network architecture designed for sequence transduction tasks like machine translation. Unlike earlier models that rely on recurrent or convolutional layers, the Transformer uses only attention mechanisms. This makes it more efficient to train and easier to parallelize while achieving better performance. Below, we break down its key ideas, mechanisms, and results.

**Core Problem and Motivation**
Traditional sequence models, such as recurrent neural networks (RNNs) or long short-term memory networks (LSTMs), process sequences step-by-step. For example, in machine translation, an RNN encodes an input sentence (e.g., English) into a sequence of hidden states, one word at a time. The decoder then generates the output sentence (e.g., German) word by word, using the hidden states. This sequential processing limits parallelization, making training slow. Additionally, RNNs struggle to capture long-range dependencies because information must pass through many steps.

The Transformer addresses these issues by removing recurrence entirely. Instead, it relies on attention, a mechanism that directly models relationships between all positions in the input and output sequences. This allows the model to process the entire sequence at once, improving speed and performance.

**Key Mechanism: Attention**
Attention computes a weighted sum of values, where the weights (attention scores) depend on the compatibility between a query and keys. In the Transformer, this is implemented as scaled dot-product attention:

Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V

Here:
- Q (queries), K (keys), and V (values) are matrices of dimensions n x d_k, m x d_k, and m x d_v, respectively.
- n is the number of queries, m is the number of key-value pairs, and d_k is the dimension of the keys and queries.
- sqrt(d_k) is a scaling factor to prevent large dot products from dominating the softmax.

Intuitively, attention determines how much each input position (key) should influence each output position (query). For example, in translation, the word "bank" in English might attend strongly to "ufer" (German for riverbank) or "bank" (financial institution), depending on context.

**Multi-Head Attention**
Instead of computing attention once, the Transformer uses multi-head attention, which runs multiple attention mechanisms in parallel. Each "head" learns different attention patterns, allowing the model to focus on various aspects of the input simultaneously. The outputs of all heads are concatenated and linearly transformed to produce the final result:

MultiHead(Q, K, V) = Concat(head_1, ..., head_h) W^O
where head_i = Attention(Q W_i^Q, K W_i^K, V W_i^V)

Here, W_i^Q, W_i^K, W_i^V, and W^O are learned weight matrices. Multi-head attention improves the model's ability to capture diverse relationships in the data.

**Positional Encoding**
Since the Transformer has no recurrence or convolution, it cannot inherently capture the order of words in a sequence. To address this, the model adds positional encodings to the input embeddings. These encodings are fixed vectors that encode the position of each word using sine and cosine functions of different frequencies:

PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))

Here, pos is the position in the sequence, i is the dimension index, and d_model is the embedding dimension. The alternating sine and cosine functions allow the model to learn relative positions effectively.

**Model Architecture**
The Transformer consists of an encoder and a decoder, each composed of stacked layers.

**Encoder**
Each encoder layer has two sub-layers:
1. Multi-head self-attention: The queries, keys, and values all come from the same input (hence "self-attention"). This allows each position to attend to all other positions in the input sequence.
2. Position-wise feed-forward network: A simple fully connected network applied to each position separately and identically. It consists of two linear transformations with a ReLU activation in between:
   FFN(x) = max(0, x W_1 + b_1) W_2 + b_2

Residual connections and layer normalization are applied around each sub-layer to stabilize training.

**Decoder**
The decoder is similar to the encoder but includes an additional sub-layer for encoder-decoder attention. This sub-layer uses the decoder's queries and the encoder's keys and values, allowing the decoder to attend to the input sequence. The decoder also masks future positions during training to prevent it from "cheating" by looking ahead.

**Training and Results**
The Transformer is trained using standard sequence-to-sequence objectives, such as cross-entropy loss. Key results include:
- On the WMT 2014 English-to-German translation task, the Transformer achieves a BLEU score of 28.4, surpassing previous best results (including ensembles) by over 2 points.
- On the WMT 2014 English-to-French task, it sets a new state-of-the-art BLEU score of 41.8 with a single model, trained in just 3.5 days on eight GPUs. This is a fraction of the training time required by earlier models.
- The Transformer also generalizes well to other tasks, such as English constituency parsing, even with limited training data.

**Assumptions and Methods**
1. The model assumes that attention mechanisms can replace recurrence and convolutions entirely. This is validated by the strong empirical results.
2. The positional encoding assumes that relative positions
```

**Judge notes:**
- *faithfulness* (5/5): All claims, numbers, and mechanisms are directly supported by the paper excerpt.
- *level_match* (5/5): Uses technical vocabulary, explains mechanisms, defines symbols in equations, and covers assumptions and main results as required for level 5.
- *coverage* (5/5): All expected topics (transformer, attention, self-attention, encoder, decoder, multi-head-attention, positional-encoding) are meaningfully addressed.
- *clarity* (5/5): Logical flow from motivation to architecture to results, with coherent structure and no confusing jumps.

---

## Commentary

**gpt-5-chat (620 tokens, 20/20):** Tight prose narrative with one well-explained equation (scaled dot-product attention). Defines every symbol it introduces and stays close to the paper without padding. The structure is single-thread reasoning — motivation → mechanism → architecture → results — which reads like a textbook section. Best balance of depth and brevity.

**Llama-4-Maverick (473 tokens, 18/20):** The most concise output, but at the cost of skipping all equations. The judge dropped its level_match to 3/5 specifically because level 5 requires "key equations with each symbol defined." Llama paraphrases the mechanism in prose ("scaled dot-product attention") without ever writing it out. This is a clear example of why Llama scores lower on level discrimination — it produces fluent but underspecified text.

**Mistral-Large-3 (1200 tokens, 20/20):** Markdown-heavy, longest by far, includes three equations (attention, multi-head, positional encoding sine/cosine). Hit the `max_completion_tokens=1200` limit mid-sentence ("...assumes that relative positions"). The thoroughness scores well but at ~2× the token cost of gpt-5-chat for the same rubric total. For a per-user-request system, this verbosity translates directly to higher latency and cost.

**Takeaway:** Llama loses level_match by omitting equations even when it has the same source material. gpt-5-chat is the most efficient producer of full-marks output. Mistral matches gpt-5 on quality but pays nearly 2× in tokens — a real production tradeoff worth flagging.

