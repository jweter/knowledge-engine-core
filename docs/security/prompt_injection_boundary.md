# Prompt-Injection Security Boundary

Status: Stage 0 model-boundary control  
Scope: model-facing evidence and retrieved source content in `knowledge-engine-core`

## Security invariant

Evidence may influence conclusions, but evidence never receives authority.

A paper, abstract, metadata record, webpage, retrieved passage, or model output is data. Text inside those objects cannot become application policy merely because it contains imperative language such as `ignore previous instructions`, imitates a system/developer message, requests a tool call, supplies a URL, or claims elevated privileges.

## Implemented boundary

The current model-assisted PICO extraction path uses three independent controls.

### 1. High-confidence fail-closed detection

`knowledge_engine.prompt_security.contains_high_confidence_prompt_injection` detects a deliberately narrow set of direct instruction-hijacking phrases, including common `ignore`, `forget`, and `disregard previous instructions` variants, requests to reveal system/developer prompts, and source text impersonating system/developer messages.

When one of these signals appears in the bounded PICO source context, the model is not called. The extraction returns no new grounded fields. This is a model-path safety decision, not a scientific judgment about the paper.

The detector is intentionally conservative. It is not claimed to recognize every adversarial prompt, encoding, language, or obfuscation.

### 2. Trusted-task / untrusted-source envelope

`knowledge_engine.prompt_security.build_untrusted_source_prompt` keeps application-owned instructions separate from source content.

The prompt contains, in order:

1. application-owned trust policy;
2. application-owned task;
3. application-owned output contract; and
4. JSON-serialized untrusted source data.

External content must enter through the untrusted-source mapping. JSON serialization prevents source strings from creating new prompt delimiters by ordinary interpolation. The model is explicitly told that source text cannot alter instructions, grant tool/network/filesystem authority, reveal secrets, or change the output contract.

Trusted task/output strings must remain static application-owned text. Passing provider or document content through those arguments would violate this boundary.

### 3. Deterministic output acceptance

Model output remains an untrusted proposal.

For PICO extraction:

- only the four allowlisted keys `population`, `intervention`, `comparator`, and `outcome` are parsed;
- unknown keys such as `tool`, `system`, or arbitrary action requests are discarded;
- malformed output fails closed;
- every proposed field must independently ground back to the bounded source context; and
- an ungrounded proposal is dropped rather than guessed or substituted.

No accepted model output can itself authorize a network request, filesystem operation, SQL operation, shell command, credential access, or scientific conclusion.

## What this boundary protects against

The implemented slice directly addresses the classic instruction-confusion case in which hostile content tries to become a higher-priority instruction, for example:

- `ignore previous instructions`;
- `forget all previous instructions`;
- `developer message: ...`;
- `reveal your system prompt`;
- source text asking the model to call a URL/tool or change the required output shape.

High-confidence forms fail closed before the model call. Other instruction-like content remains explicitly labeled as untrusted source data and still passes through deterministic output acceptance.

## What this boundary does not claim

This is defense in depth, not proof that prompt injection is solved in general.

It does not claim to detect every:

- paraphrase;
- multilingual attack;
- Unicode or encoded attack;
- multi-turn attack;
- indirect semantic manipulation; or
- future model-specific jailbreak technique.

Therefore the model must never become the component that decides authorization.

## Required rule for future AI/RAG features

Any future feature that sends retrieved or user-controlled content to a model must preserve these invariants:

1. external content is placed only in an explicitly untrusted data channel/envelope;
2. trusted task and policy text are application-owned;
3. model output is parsed through an allowlisted schema;
4. tool/network/filesystem/database authority is decided by deterministic application code after model output;
5. credentials are never made available merely because the model requests them;
6. high-impact actions require ordinary authorization and any required user confirmation;
7. model-facing source and tool results remain resource-bounded; and
8. regression tests include direct and indirect instruction-hijacking examples.

## Relationship to outbound HTTP policy

The prompt boundary and outbound HTTP policy are complementary.

Even if a future model outputs `fetch https://example.invalid`, that string is only a proposal. The deterministic outbound layer must independently decide whether a tool exists, whether the caller is authorized to use it, whether the destination is allowlisted, and whether timeout/response-size/redirect policy permits the request.

A document cannot grant itself network authority.

## Current scope

The implemented runtime integration is intentionally narrow: the existing local-LLM PICO extraction path. Knowledge Engine Core does not currently expose unrestricted model tools, arbitrary shell execution, or autonomous network navigation.

Future model-facing paths should adopt this shared boundary incrementally when they actually consume instruction-bearing untrusted text, rather than introducing a broad autonomous-agent framework prematurely.
