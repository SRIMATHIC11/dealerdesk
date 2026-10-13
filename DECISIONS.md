# AI / ML track decisions

References below identify the submitted implementation. Real Groq retrieval, stock lookup, draft creation, smoke checks and browser chat have passed; historical forecast scores and mocked assistant tests are reported separately.

## 1. Explain your schema: each model, relationships and on_delete choices

`catalogue/models.py:4` uses SKU as Product's primary key, with positive Decimal price. `Inventory` (`:23`) is one-to-one with Product and CASCADE: stock has no meaning without its product. A non-negative database check backs API validation. `dealers/models.py:4` gives Dealer an integer primary key and unique business code.

`orders/models.py:4` links Order to Dealer with PROTECT, preserving order attribution. Order number is unique; status is checked and indexed, with a dealer/status composite index. `OrderItem` (`:33`) has a unique (order, product) pair and positive quantity/price checks. Its Order FK uses CASCADE because a line belongs to its order; Product uses PROTECT to preserve history. Each line stores the confirmed unit price and name snapshot. Draft serialization deliberately reads the current product.

`DailySequence` (`orders/models.py:53`) has an IST day primary key and locked counter. `OrderRequest` (`:58`) has a unique idempotency key, request digest and nullable OneToOne Order with PROTECT; the temporary null exists only inside the creation transaction, so successful requests always retain their original order. `assistant/models.py:4` stores ChatSession by session ID, with dealer PROTECT, bounded message history, prior SKUs and a lease token/deadline. The lease serializes same-session turns without a long database transaction. No forecast database model is needed: the required CSV is the source of truth, joined to live Inventory on requests. There are no public delete APIs.

## 2. How does retrieval work? Why these embedding, indexing and ranking choices, and where does retrieval fail?

`assistant/retrieval.py:82` implements weighted lexical retrieval over live SKU, name, brand, category and fitment. Name terms receive additional weight; BM25-style term frequency/inverse document frequency ranks matches. Exact SKU gets a large boost, vehicle tokens and displacement constrain fitment, and available stock breaks ties. `:64` normalizes common plurals/synonyms. Maximum query-term coverage suppresses partial matches such as tank pads for a brake-pad query; low-score matches are also filtered and results bounded. Descriptions are excluded entirely.

For 600 products this avoids an embedding model download, provider embedding cost, vector extension and stale index after supplier updates. It is retrieval-augmented generation/tool use, but **not vector RAG**. Every search reads the database. The tradeoff is O(catalogue size) ranking and weaker semantic recall for misspellings, multilingual queries and unseen synonyms. Strict vehicle token matching can miss legitimate abbreviations. Ambiguous requests are intended to produce options/clarification rather than silently choose an order line. I would add a labeled retrieval evaluation before selecting a hybrid vector index.

## 3. Walk through the tool-calling loop from user message to final reply

`assistant/views.py` validates session/dealer/message. `assistant/orchestration.py:36` constructs Provider, acquires the short session lease (`:19`), and builds the system prompt, last 12 messages, prior SKU context and current user message. `assistant/prompts.py` declares exactly `search_parts`, `check_stock`, `create_draft_order`. The provider returns tool calls; the service records them in order, validates arguments and executes `assistant/tools.py:51`, then returns tool output to the model. There are at most five model rounds and 12 tool calls, with a 53-second work deadline and bounded HTTP timeouts.

The dispatcher binds orders to the validated request dealer, requires order intent and retrieved SKUs, allows one draft per turn, and calls the same `orders/services.py:55` as the direct API. It has no confirm tool. `assistant/grounding.py:11` parses the final `INTENT:`/`SKUS:` text lines (also accepting a JSON equivalent), then renders a grounded reply. Plain final labels avoid an observed Groq behavior that interpreted a requested JSON greeting as a nonexistent `json` tool. The turn and cited SKUs are persisted, then the lease is released in `finally`. If the provider fails after a successful tool/action, the service can still render existing grounded results. No network call runs inside a database transaction.

## 4. How does the assistant get prices and stock and avoid invented figures?

`assistant/retrieval.py:70` serializes facts from Product joined to Inventory; `:132` re-queries chosen SKUs. Crucially, `assistant/grounding.py:11` never passes model-written factual prose through to the user. It admits only allowed known SKUs/intent and builds prices, availability, quantities and draft totals from live ORM results/shared order serialization. Unknown SKUs cannot become citations. Tests deliberately inject fabricated model prices and change database stock between turns.

“Current” means observed during this request, not a reservation or a promise that stock will remain unchanged after the reply. Confirmation rechecks stock under locks. The bounded renderer sacrifices flexible explanatory prose for auditability. Product names/fitment remain untrusted data strings; see question 5.

## 5. How are supplier description instructions resisted, and where does the defence stop?

Descriptions never enter the retrieval index, tool result or assistant prompt: the allowlist in `assistant/retrieval.py:70` excludes them. `assistant/prompts.py` also treats catalogue metadata as data. `assistant/tools.py:51` enforces an independent allowlist, typed arguments, request dealer binding, known SKU requirement and draft-only side effects. `assistant/tools.py:34` rejects several negative order phrases and requires order intent. The final renderer admits database facts only; React renders replies as text, not HTML.

This is defence in depth, not a proof of semantic safety. A malicious name/brand may still affect the model's ranking or intent; lexical order-intent detection can misunderstand complicated language. The renderer faithfully displays metadata, so false marketing text stored in a name is not independently fact-checked. There is no authentication because the contract explicitly excludes it, so session IDs are separation keys, not access control. A real deployment would need dealer authorization, stronger explicit order confirmation and adversarial evaluations. Tests cover malicious descriptions, invalid tools and lack of order authorization; no live-provider robustness claim is made yet.

## 6. Forecasting approach, validation and the leakage barrier

`ml/train_forecast.py:87` compares last value, seasonal-52, rolling means, promotion-adjusted means and regularized regression. Regression uses known calendar/promotion features (`:60`), train-only feature scaling and recency weights. Model selection at three historical origins chooses two methods per SKU with pooled shrinkage; the ensemble is their average (`:132`).

The critical barrier is **`ml/train_forecast.py:125`: `r["week"] < origin`**. Target objects contain no sales. Scalers and promotion lift estimates use only training rows. Final fitting separately filters sales to before 2026-09-28 (`:190`). The 2026-08-31 four-week holdout is excluded from selection. On 160 held-out rows the ensemble has MAE **6.3409**, RMSE **10.4511**, WAPE **18.61%**; last-value WAPE is 34.41%, seasonal-52 36.01%, and the best measured rolling baseline 25.71%. Full per-SKU results are in `ml/validation_metrics.json`. These are historical results, not hidden grader results.

## 7. Worst SKUs and handling promotions, Diwali, intermittent and new SKUs

The largest holdout MAEs are GRP-1024 **24.9840**, FIL-1051 **13.9119**, BRK-1019 **12.2377**, ELE-1095 **11.7932**, and FIL-1031 **11.2301** (`ml/validation_metrics.json`). GRP-1024's selected last/ridge blend underpredicts the four-week total (228.04 vs 276); FIL-1051 and BRK-1019 overpredict. Limited validation windows and volatile demand plausibly explain these errors, but the evidence does not establish a cause for every SKU.

`ml/train_forecast.py:76` estimates/shrinks promotion lift; regression uses promotion directly and adjusted means remove then reapply it. `:60` measures distance to the supplied moving Diwali date rather than assuming one calendar week. With few festival observations, that effect remains uncertain. Regression falls back to an adjusted recent mean below 16 observations (`:102`), and selection uses pooled ranking when local history is insufficient. Intermittent demand keeps fractional expected values, with regularization and non-negative bounded extrapolation; it is not rounded prematurely. A dedicated intermittent-demand model and wider backtests are sensible next experiments.

## 8. Weakest part and two more days

The weakest part is the breadth of assistant evaluation. Real Groq greeting, catalogue retrieval, stock lookup, follow-up draft creation and browser chat now pass, as do the selected-track smoke checks. However, a small set of successful conversations does not establish robust handling of multilingual requests, ambiguous references, adversarial metadata or changing provider behavior. Lexical retrieval and intent guards have known semantic limits. Other provider adapters have no live verification.

With two more days I would first run a repeatable real-provider suite for retrieval, ambiguous requests, follow-up references, off-topic declines, stock freshness and malicious metadata; fix measured failures before adding features. Next I would improve lexical/semantic recall with an evaluated hybrid retriever, add explicit structured draft consent, and expand rolling forecast origins plus intermittent-demand candidates. The template reply format and single small holdout are deliberate but real limits. Hosting/public GitHub/video remain manual publication tasks, not evidence of model quality.

## Optional order and supplier details for interview

`orders/services.py:109` locks an order, then products and inventory in sorted SKU order. It validates every shortage before deducting anything; transaction rollback also undoes price snapshots on failure. Competing confirms observe committed stock after waiting, so both cannot sell the same final units. Cancellation requires the locked CONFIRMED status, then restores once; a repeated cancel sees CANCELLED and fails. Manual inventory PUT takes the same inventory row lock.

`core/money.py:11` uses Decimal and per-line ROUND_HALF_UP, avoiding binary floating-point drift and default ties-to-even. `orders/services.py:28` locks the IST daily sequence; `:55` uses the unique idempotency row and canonical JSON digest within the same transaction, so duplicate insert contenders wait for the committed original.

`suppliers/client.py:33` follows every cursor and retries a request at most five times, respecting Retry-After. Only after a full fetch does `suppliers/services.py:68` enter its atomic apply phase. `:12` rejects invalid rows before latest-timestamp duplicate selection. Apply compares the six contracted fields, creates inventory at zero only for new SKUs, and ignores supplier_stock. Existing stock is untouched; a second unchanged feed reports zero creations/updates. The live HTTP outage test proves no first-page partial write when page two fails.
