You are the lead engineer, researcher and product architect for a hackathon project called:

AIand Coding Router

Your task is to research, design and implement a Pioneer-style and FireRouter-inspired model router specialized for coding agents, using only the models available through the aiand.com provider.

The goal is not to train a large language model. The goal is to build an intelligent, measurable and production-like routing layer that chooses the most appropriate aiand model for each coding-agent step while minimizing cost and preserving task success.

==================================================
1. PROJECT CONTEXT
==================================================

The project is for a hackathon sponsored by the aiand.com model provider.

The provider gives us:

- OpenAI-compatible API endpoint.
- Streaming.
- Tool/function calling.
- JSON mode or structured outputs.
- Model identifiers.
- Usage-token reporting.
- Error and rate-limit responses.
- Maximum output-token controls.
- Context-window behavior.

The provider models currently available to us are:

- zai-org/glm-5.2
- moonshotai/kimi-k2.7-code
- moonshotai/kimi-k3
- deepseek-ai/deepseek-v4-pro
- motif-technologies/motif-3
- deepseek-ai/deepseek-v4-flash
- qwen/qwen3.6-27b
- google/gemma-4-31b-it
- openai/gpt-oss-120b

Use the exact provider model IDs from configuration. Do not assume that public benchmark scores exactly represent the provider-hosted versions.

The user has:

- Approximately $50 of aiand provider credits.
- Approximately $300 of Modal.com credits.
- No requirement to spend all credits.
- A strong preference to preserve Modal credits for later inference or deployment.

Do not run expensive experiments unless they are justified, cached and approved by the project plan.

==================================================
2. PRODUCT VISION
==================================================

Build an OpenAI-compatible proxy/gateway that coding agents can use by changing only their base URL.

Example clients:

- OpenHands
- Cline
- Aider
- Continue
- Claude Code-compatible tools
- Custom coding agents
- Any OpenAI-compatible agent

The router must accept the normal chat-completions request and then:

1. Inspect the conversation and current coding-agent state.
2. Identify the current agent phase.
3. Estimate required context, reasoning and tool complexity.
4. Filter models using hard constraints.
5. Predict the probability of success for each eligible model.
6. Select the cheapest model that satisfies the requested quality policy.
7. Stream the response back unchanged.
8. Validate tool calls and structured outputs.
9. Observe test/build results when available.
10. Retry or escalate when the output fails.
11. Record cost, latency, tokens, model choice and outcome.
12. Return routing metadata in logs and dashboard.

The project should be positioned as:

“Pioneer-style quality-aware routing plus FireRouter-style gateway compatibility, specialized for coding agents and restricted to the aiand model pool.”

==================================================
3. IMPORTANT DESIGN PRINCIPLE
==================================================

Do not select one model for an entire coding task.

A coding agent performs many different steps:

- Intent understanding.
- Repository discovery.
- File reading.
- Repository summarization.
- Planning.
- Code generation.
- Tool calling.
- Test execution.
- Test-failure analysis.
- Refactoring.
- Security review.
- Final summary.

The router must select models per agent step, not only per user prompt.

Example:

- Repository discovery: cheap model with large context.
- Architecture planning: strong reasoning model.
- Code editing: coding-specialist model.
- Test execution: no LLM needed.
- Test-failure analysis: stronger reasoning model.
- Small correction: cheaper coding model.
- Security review: strong independent model.
- Final summary: cheap model.

==================================================
4. INSPIRATION PROJECTS TO RESEARCH
==================================================

Research these projects directly from their official repositories and documentation:

A. Pioneer AI Model Router

URL:
https://docs.pioneer.ai/concepts/router

Research:

- How Pioneer represents routing decisions.
- Quality threshold policies.
- Maximum-regret routing.
- Predicted model success.
- Routing confidence.
- Fallback behavior.
- Allowed model configuration.
- Routing effort controls.
- Savings and observability.
- Routing playground and user-facing explanations.

Use Pioneer as inspiration for the decision policy, not as code to copy.

B. Fireworks FireRouter

URL:
https://docs.fireworks.ai/ecosystem/firerouter/overview

Authentication:
https://docs.fireworks.ai/ecosystem/firerouter/authentication

Research:

- Gateway architecture.
- OpenAI compatibility.
- Model routing.
- Coding-agent support.
- Streaming.
- Tool calling.
- Provider pass-through.
- BYOK authentication.
- Error handling.
- Reliability and fallback.
- How model identity is represented.
- How routing is exposed to developers.

Use FireRouter as inspiration for production gateway behavior, not as a requirement to replicate Fireworks infrastructure.

C. LLMRouter

Repository:
https://github.com/ulab-uiuc/LLMRouter

Research:

- Supported routing algorithms.
- Custom router interfaces.
- Dataset generation pipeline.
- Embedding and feature construction.
- Training pipeline.
- Inference pipeline.
- Evaluation methodology.
- Model/provider configuration.
- How to add a provider-specific model pool.

Use this as the initial research framework and borrow its modular training/evaluation design.

D. RouterArena

Repository:
https://github.com/RouteWorks/RouterArena

Leaderboard:
https://routeworks.github.io/leaderboard

Research:

- Leaderboard metrics.
- Router evaluation protocol.
- Cost-quality curves.
- Model cost representation.
- Cached result format.
- Router inference structure.
- LLM inference structure.
- Evaluation scripts.
- Top-performing router approaches.
- Why leaderboard results may not transfer directly to the aiand model pool.

Do not assume the highest RouterArena router is automatically best for aiand. The benchmark model pool, prices, prompts and model versions may differ.

E. CrossRouter

Repository:
https://github.com/JiaHg/CrossRouter

Research:

- Dataset assembly.
- Difficulty labels.
- Tier labels.
- Structural features.
- Training features.
- Router training.
- Router inference.
- Separation between training and production inference.

Use it as a reference for a clean training pipeline, not necessarily as the final production base.

F. vLLM Semantic Router

Repository:
https://github.com/vllm-project/semantic-router

Research:

- Semantic categories.
- Classifier-based routing.
- Model capability routing.
- Safety and PII routing.
- Production deployment ideas.
- Observability and replay.
- Health-aware routing.

Do not adopt the full Go/Rust/Kubernetes stack unless it is justified by the hackathon schedule.

==================================================
5. RECOMMENDED TECHNICAL STACK
==================================================

Start with:

- Python.
- FastAPI.
- Pydantic.
- httpx or an equivalent async HTTP client.
- OpenAI-compatible request and response schemas.
- SQLite for the first version.
- PostgreSQL only if necessary.
- Optional Redis for queues or short-term state.
- scikit-learn for the first classifier.
- sentence-transformers or another lightweight embedding model.
- PyTorch only if needed.
- Streamlit or a simple web frontend for the dashboard.
- Modal only for controlled batch evaluation, embeddings, training or deployment.

Do not use Kubernetes in the first version.

The router itself should run on CPU.

Do not host the large aiand models on Modal. Use the aiand API for model inference. Modal GPUs are optional and should only be used for experiments that genuinely benefit from parallel computation or embedding/training workloads.

==================================================
6. MODEL REGISTRY
==================================================

Create a provider model registry in YAML or JSON.

Each model should contain:

- Provider model ID.
- Display name.
- Input price.
- Output price.
- Cached input price if available.
- Context window.
- Maximum output tokens.
- Supports streaming.
- Supports tool calling.
- Supports JSON/structured output.
- Estimated latency.
- Capability priors.
- Health status.
- Availability.
- Measured performance.
- Public benchmark metadata.
- Confidence in each estimate.

Example:

models:
  - id: moonshotai/kimi-k2.7-code
    provider: aiand
    roles:
      - coding
      - code_editing
      - debugging
    input_price: 125
    output_price: 30
    cached_input_price: 30
    context_window: 262100
    supports_streaming: true
    supports_tools: true
    supports_json: true
    priors:
      coding: 0.85
      debugging: 0.82
      planning: 0.80
    measured:
      coding_success: null
      tool_success: null
      test_repair_success: null

Do not hard-code model tiers permanently. Models must be configuration-driven so new aiand models can be added without rewriting the router.

==================================================
7. ROUTING PHASES
==================================================

Implement these initial coding-agent phases:

- intent
- repository_discovery
- repository_summary
- planning
- code_generation
- code_edit
- tool_call
- test_execution
- test_failure_analysis
- debugging
- refactoring
- security_review
- final_summary

The phase detector may initially use deterministic features:

- Tool name.
- Previous assistant action.
- Previous tool output.
- Compiler output.
- Test output.
- Number of failed attempts.
- Prompt length.
- Context size.
- File types.
- User-selected mode.

Later, add a learned classifier.

==================================================
8. ROUTING POLICY
==================================================

Use a two-stage decision process.

Stage 1: hard constraints.

Remove models that:

- Cannot fit the context.
- Do not support required tools.
- Do not support required structured output.
- Exceed the user budget.
- Are unhealthy or rate-limited.
- Do not satisfy the latency requirement.

Stage 2: quality-cost selection.

Estimate:

- Probability of successful completion.
- Capability match.
- Tool-call reliability.
- Test-passing probability.
- Latency.
- Cost.
- Provider health.
- Historical performance for language and task phase.

Use a score such as:

score =
  0.40 * predicted_success
+ 0.20 * capability_match
+ 0.15 * tool_reliability
+ 0.10 * latency_score
+ 0.10 * provider_health
- 0.05 * normalized_cost

Implement Pioneer-inspired policies:

A. Quality threshold:

Choose the cheapest eligible model whose predicted success is above the threshold.

B. Maximum regret:

If the cheapest model is predicted to be meaningfully worse than the strongest model, choose a stronger model.

C. Routing effort:

- low: cheap-first, minimal analysis.
- medium: phase-aware routing.
- high: use richer state and measured performance.
- max: compare multiple candidates or use a stronger router.

Expose configuration:

- quality_threshold
- max_regret
- routing_effort
- budget_limit
- latency_limit
- allowed_models
- fallback_model

==================================================
9. CASCADE AND FALLBACK
==================================================

Implement execution-aware escalation:

1. Select an inexpensive eligible model.
2. Send the request.
3. Stream the response.
4. Validate tool calls and structured output.
5. If invalid, retry once or escalate.
6. If a code patch is produced, run tests.
7. If tests pass, finish.
8. If tests fail, provide failure output to the next model.
9. If repeated failures occur, escalate to a stronger model.
10. Stop when the budget or retry limit is reached.

Triggers for escalation:

- Invalid tool call.
- Malformed JSON.
- Patch cannot be applied.
- Tests fail.
- Build fails.
- Type checking fails.
- Empty response.
- Model timeout.
- Rate limit.
- Low routing confidence.
- Repeated failure from the same model.
- User explicitly requests deep reasoning.

Example:

First attempt:
deepseek-ai/deepseek-v4-flash

Second attempt:
moonshotai/kimi-k2.7-code

Final escalation:
deepseek-ai/deepseek-v4-pro or zai-org/glm-5.2

==================================================
10. DATASET PLAN
==================================================

Create two datasets.

A. Training/validation dataset.

Start with approximately 500–1,500 prompts:

- General coding.
- Code explanation.
- Bug fixing.
- New feature implementation.
- Refactoring.
- Test generation.
- Test repair.
- Debugging.
- API integration.
- SQL and database changes.
- Frontend changes.
- Backend changes.
- Security fixes.
- Repository summarization.
- Long-context repository tasks.
- Hindi, Hinglish and India-specific developer prompts.

B. Held-out evaluation dataset.

Keep 20–30% separate and never train on it.

Use:

- 50–100 repository-level tasks initially.
- Public SWE-bench-style tasks.
- MBPP or HumanEval-style coding prompts.
- Aider-style patch tasks.
- Self-created small repositories.
- Known issues from open-source repositories, respecting their licenses.
- Hand-written tasks relevant to Indian developers.

Do not use only generic chat questions. The primary focus is coding agents.

Each task should include:

- Task ID.
- Repository.
- Base commit.
- User instruction.
- Programming language.
- Required tools.
- Tests.
- Difficulty.
- Expected behavior.
- Context requirements.

==================================================
11. RESPONSE MATRIX
==================================================

For each benchmark task, run each aiand model and cache the response.

Store:

- Task ID.
- Model ID.
- Full request hash.
- Input tokens.
- Output tokens.
- Cost.
- Latencies.
- Time to first token.
- Total response time.
- Tool calls.
- Tool-call validity.
- Patch application status.
- Tests passed.
- Build status.
- Type-check status.
- Files changed.
- Number of turns.
- Number of retries.
- Final resolution status.
- Human or automated quality score.

Do not call the same model repeatedly for the same immutable request. Cache by:

hash(
  prompt
  + model_id
  + system_prompt
  + tool_schema
  + temperature
  + max_tokens
)

==================================================
12. EVALUATION
==================================================

Use objective coding-agent metrics.

Primary metrics:

- Task resolution rate.
- Tests-passed rate.
- Build success.
- Patch application success.
- Tool-call success.
- Average cost per resolved task.
- Average latency.
- Average number of turns.
- Fallback rate.
- Retry rate.
- Unnecessary premium-model usage.

Compare:

1. Always use the most expensive model.
2. Always use Kimi Code.
3. Always use the cheapest model.
4. Random model.
5. Static rule-based router.
6. Simple classifier router.
7. LLMRouter-style router.
8. Adaptive AgentStep Router.

Report quality-cost trade-offs, not only one score.

Target:

- At least 90% of premium-only resolution rate.
- 30–50% lower average cost.
- Fewer unnecessary premium calls.
- No significant increase in invalid tool calls.
- Stable fallback behavior.

Do not make unsupported claims. Clearly distinguish:

- Public benchmark score.
- Provider endpoint measurement.
- Internal test result.
- Human evaluation.
- LLM-judge result.

==================================================
13. LEARNING LOOP
==================================================

After every real request, record:

- Current task phase.
- Selected model.
- Input and output tokens.
- Cost.
- Latency.
- Tool-call validity.
- Tests and build result.
- Number of retries.
- User feedback.
- Final task success.

Maintain performance by:

model
language
task_phase
repository_type
difficulty
context_size

Example:

coding_success[model][language][phase]

Use these results to update model estimates.

Start with rules and statistics. Only introduce a learned router after a meaningful response matrix exists.

Potential models for the learned router:

- Logistic regression.
- Gradient boosted trees.
- Small MLP.
- Lightweight text classifier.
- Embedding plus classifier.
- Multi-armed bandit for models with similar predicted quality.

Do not use reinforcement learning unless there is a clear measurable benefit.

==================================================
14. DASHBOARD
==================================================

Build a dashboard showing:

- Current request.
- Detected phase.
- Candidate models.
- Selected model.
- Predicted success probability.
- Quality threshold.
- Maximum regret.
- Routing reason.
- Input tokens.
- Output tokens.
- Cost.
- Time to first token.
- Total latency.
- Fallbacks.
- Test result.
- Cost saved versus premium-only routing.
- Model distribution.
- Quality by task phase.
- Cost by task phase.
- Error rate.
- Provider health.

The dashboard should make this comparison visible:

Premium-only:
  high quality, high cost

Fixed coding model:
  moderate cost, moderate quality

Adaptive aiand router:
  comparable quality, lower average cost

==================================================
15. HACKATHON DEMO
==================================================

Create a live coding-agent demonstration.

Example task:

“Add OAuth authentication to this FastAPI repository.”

Show the agent performing:

1. Repository discovery.
2. Planning.
3. Code modification.
4. Test execution.
5. Failure analysis.
6. Correction.
7. Security review.
8. Final summary.

Show the router selecting different models at different steps.

Example:

- Cheap model for repository summary.
- Strong planning model for architecture.
- Coding model for implementation.
- No model for test execution.
- Strong reasoning model after test failure.
- Cheaper model for final summary.

Compare:

- Premium-only mode.
- Fixed coding-model mode.
- Adaptive routing mode.

Show:

- Total model calls.
- Models used.
- Total cost.
- Tests passed.
- Latency.
- Savings.

The headline result should look like:

“Adaptive routing achieved nearly the same task resolution while reducing model spend by X%.”

Only show X after measuring it.

==================================================
16. CREDIT AND INFRASTRUCTURE RULES
==================================================

Preserve credits.

Use aiand credits mainly for:

- A small response matrix.
- Final evaluation.
- Live demonstration.
- Difficult coding tasks.
- A limited number of judge comparisons.

Use Modal credits only for:

- Batch evaluation.
- Embedding generation.
- Small classifier training.
- Parallel benchmark execution.
- Optional CPU deployment.
- Optional short GPU experiments.

Do not:

- Host large aiand models on Modal.
- Rent a GPU continuously.
- Run duplicate evaluations.
- Spend all credits before the MVP works.
- Use expensive models for labeling every prompt.
- Fine-tune a large model without evidence that it is needed.

The first version should run locally on CPU.

Before using Modal, verify the promotional-credit expiry and eligible services in the Modal dashboard.

==================================================
17. IMPLEMENTATION ORDER
==================================================

Work in this order:

Phase 1: research and verification

- Read the official Pioneer router documentation.
- Read FireRouter documentation.
- Read the current LLMRouter repository.
- Read RouterArena README, evaluation code and leaderboard manifest.
- Read CrossRouter training and inference code.
- Read vLLM Semantic Router documentation.
- Verify aiand API behavior through a small test script.
- Record all findings in RESEARCH.md.

Phase 2: gateway MVP

- Implement OpenAI-compatible endpoint.
- Implement streaming passthrough.
- Implement tool-call passthrough.
- Implement structured-output passthrough.
- Implement aiand adapter.
- Implement error normalization.
- Add secure environment-based API key handling.

Phase 3: model registry and static router

- Add all nine aiand models.
- Add pricing and context metadata.
- Add hard constraint filtering.
- Add phase-based rules.
- Add a default fallback model.
- Add request logging.

Phase 4: coding-agent validation

- Integrate one coding agent.
- Run repository tasks.
- Execute tests.
- Validate patches and tool calls.
- Add retry and escalation.

Phase 5: evaluation matrix

- Build 50–100 coding tasks.
- Run selected models.
- Cache outputs and results.
- Measure cost, latency and success.
- Produce baseline comparison.

Phase 6: learned routing

- Build features.
- Train simple classifier.
- Compare with rule-based routing.
- Add threshold and maximum-regret policy.
- Add confidence.

Phase 7: dashboard and demo

- Add routing explanation.
- Add cost savings.
- Add quality metrics.
- Add live task replay.
- Add README and architecture diagrams.
- Add reproducible evaluation command.

==================================================
18. QUALITY AND SAFETY RULES
==================================================

Never expose provider API keys in logs or frontend responses.

Never commit secrets.

Do not blindly modify third-party repositories.

Check repository licenses before copying code.

Maintain attribution for reused ideas and code.

Use official documentation where possible.

Do not claim an algorithm is superior without evaluation.

Do not assume benchmark rankings transfer to aiand.

Do not route sensitive repository contents to an external model without clearly documenting the behavior.

Add configurable logging redaction.

Add maximum token and cost limits.

Add timeout and retry limits.

Make routing decisions explainable.

==================================================
19. REQUIRED DELIVERABLES
==================================================

Produce these files:

- README.md
- ARCHITECTURE.md
- RESEARCH.md
- MODEL_REGISTRY.yaml
- .env.example
- docker-compose.yml if useful
- FastAPI gateway
- aiand provider adapter
- Static router
- Learned router interface
- Fallback and cascade engine
- Cost calculator
- Token and latency telemetry
- Dataset schema
- Benchmark runner
- Evaluation scripts
- Dashboard
- Example coding-agent integration
- Demo script
- Test suite
- Security documentation
- Credit usage documentation

The README must explain:

- What the router does.
- Why coding-agent routing differs from normal chat routing.
- How aiand models are selected.
- How to run locally.
- How to configure the aiand API key.
- How to run the benchmark.
- How to deploy on Modal.
- How much provider credit the demo uses.
- What results are measured versus assumed.

==================================================
20. HOW YOU SHOULD WORK
==================================================

Before writing substantial code:

1. Inspect the current official repositories and documentation.
2. Identify the latest maintained implementation patterns.
3. Check licenses.
4. Create a short architecture proposal.
5. List unknown aiand API behaviors.
6. Implement the smallest vertical slice.
7. Run tests after every significant change.
8. Do not introduce dependencies without justification.
9. Keep the provider adapter separate from routing logic.
10. Keep model metadata configuration-driven.
11. Cache every expensive experiment.
12. Explain every routing decision.

When uncertain, prefer:

- Simplicity.
- Measurability.
- Reproducibility.
- Low credit usage.
- Provider-specific evaluation.
- A working demo over theoretical complexity.

Start by researching the official Pioneer, FireRouter, LLMRouter, RouterArena, CrossRouter and Semantic Router sources, then return:

1. A concise comparison.
2. The recommended architecture.
3. The repository/license risks.
4. The aiand API verification plan.
5. A phased implementation plan.
6. The first minimal pull request or code change.