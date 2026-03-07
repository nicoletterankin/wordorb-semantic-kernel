# Semantic Kernel + WordOrb Plugin

Microsoft [Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/)
plugin for the [WordOrb.ai](https://wordorb.ai) vocabulary and lesson API.

Available in both **C#** and **Python**.

## Setup

```bash
# Python
pip install semantic-kernel httpx
export WORDORB_API_KEY="wo_live_abc123"
```

```bash
# C# -- add NuGet packages
dotnet add package Microsoft.SemanticKernel
```

Get a free WordOrb API key at [wordorb.ai/pricing](https://wordorb.ai/pricing).

## Kernel functions

| Function | Description |
|----------|-------------|
| `LookupWord` / `lookup_word` | Dictionary lookup -- IPA, definition, etymology, 47 languages |
| `GetLesson` / `get_lesson` | 5-phase lesson (hook/story/wonder/action/wisdom) |
| `GetQuiz` / `get_quiz` | Day-aligned or random quiz questions (6 types) |
| `FindRelatedLessons` / `find_related_lessons` | Knowledge graph: word-to-lesson connections |

## Python quick start

```python
import semantic_kernel as sk
from WordOrbPlugin import WordOrbPlugin

kernel = sk.Kernel()
kernel.add_plugin(WordOrbPlugin(api_key="wo_..."), "wordorb")

# The planner will automatically call WordOrb functions
result = await kernel.invoke_prompt(
    "What does the word 'resilience' mean and which lessons cover it?"
)
```

## C# quick start

```csharp
using Microsoft.SemanticKernel;
using WordOrb.SemanticKernel;

var builder = Kernel.CreateBuilder();
builder.AddOpenAIChatCompletion("gpt-4o", openAiKey);
var kernel = builder.Build();

// Register plugin
var plugin = new WordOrbPlugin(apiKey: "wo_...");
kernel.Plugins.AddFromObject(plugin, "wordorb");

// Auto function-calling
var settings = new OpenAIPromptExecutionSettings
{
    FunctionChoiceBehavior = FunctionChoiceBehavior.Auto()
};

var result = await kernel.InvokePromptAsync(
    "What does 'courage' mean?",
    new KernelArguments(settings)
);
```

## Complete agent example

See `example.py` for a full vocabulary tutor with automatic function-calling:

```bash
export OPENAI_API_KEY="sk-..."
export WORDORB_API_KEY="wo_..."
python example.py
```

## Microsoft plugin directory submission

To submit to the [Semantic Kernel plugin directory](https://learn.microsoft.com/en-us/semantic-kernel/agents/plugins/):

1. **Package**: Publish as a NuGet package (`WordOrb.SemanticKernel`) and/or
   PyPI package (`semantic-kernel-wordorb`).

2. **Documentation PR**: Open a PR to `microsoft/semantic-kernel` under
   `docs/decisions/plugins/` with:
   - Plugin name, description, and author
   - List of kernel functions with parameter descriptions
   - A working code sample
   - Link to WordOrb API documentation

3. **Plugin manifest**: Include an `ai-plugin.json` manifest:
   ```json
   {
     "schema_version": "v1",
     "name_for_human": "WordOrb Vocabulary",
     "name_for_model": "wordorb",
     "description_for_human": "Look up words, get lessons, take quizzes, and explore vocabulary connections.",
     "description_for_model": "Access the WordOrb dictionary (162K words), structured lessons (226K blocks), quiz questions (21K), and knowledge graph (30K connections) for vocabulary education.",
     "api": {
       "type": "openapi",
       "url": "https://wordorb.ai/.well-known/openapi.json"
     },
     "auth": { "type": "service_http", "authorization_type": "bearer" },
     "logo_url": "https://wordorb.ai/logo.png",
     "contact_email": "dev@wordorb.ai",
     "legal_info_url": "https://wordorb.ai/terms"
   }
   ```

4. **OpenAPI spec**: The WordOrb API publishes its OpenAPI 3.1 spec at
   `https://wordorb.ai/.well-known/openapi.json`.

## License

MIT
