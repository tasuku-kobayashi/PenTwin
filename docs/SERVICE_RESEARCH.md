# Writing-naturalness services: design choices for PenTwin (2026-10-26)

This is a comparison of publicly documented product features, not a performance benchmark or endorsement. No pilot writer, document, or private paper was sent to any service.

| Product and primary documentation | Observed feature | PenTwin decision |
| --- | --- | --- |
| [Grammarly voice profile](https://support.grammarly.com/hc/en-us/articles/23153676821773-View-and-customize-your-voice-profile) | Separates longer documents from messages and lets a writer inspect and remove detected voice elements. | Consider a human-editable, section-scoped profile. A profile is useful only if blinded author-likeness ratings support it. |
| [QuillBot Fluency and Academic modes](https://help.quillbot.com/hc/en-us/articles/35854318883351-What-are-modes-in-the-Quillbot-Paraphraser-and-how-do-I-use-them) | Fluency aims to make few changes; Academic aims for a research tone. | Test restrained edits and a generic academic rewrite as separate style controls. |
| [Jenni Reviews](https://docs.jenni.ai/docs/ai-tools/reviews/) | Tone of Voice checks word choice, sentence structure, formality, clarity and readability; a PDF can be a style reference. | Evaluate these dimensions separately. PenTwin's source corpus remains local; this is not a proposal to upload private PDFs to Jenni. |
| [Paperpal paraphrasing](https://paperpal.com/blog/academic-writing-guides/frequently-asked-questions-paraphrasing) and [Writefull for Word](https://help.writefull.com/writefull-for-word--user-guide) | Academic language and editing assistance. | Use generic scholarly editing as a comparison condition; marketing claims cannot establish author-specific resemblance. |
| [Undetectable AI API](https://help.undetectable.ai/en/article/humanization-api-v2-p28b2n/) | Optimizes a rewrite toward detector-oriented humanization. | Reject detector scores and detector evasion as PenTwin objectives. They do not test a specific researcher's voice. |

The useful ideas are an inspectable voice profile and a comparison against generic academic polish. The service documentation establishes features, not author-likeness performance. PenTwin does not optimize detector scores. In masked same-content comparisons, rate the target writer's voice, distinctiveness and naturalness separately; scientific verification is outside this project. Earlier experiments with exact protected spans are historical and no longer exposed by the MCP server.
