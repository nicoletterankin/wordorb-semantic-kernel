// =============================================================================
// WordOrbPlugin.cs -- Microsoft Semantic Kernel plugin for WordOrb.ai
//
// Provides four kernel functions:
//   - LookupWord       -- dictionary lookup (162K words, 47 languages)
//   - GetLesson        -- structured 5-phase lesson
//   - GetQuiz          -- quiz / assessment questions
//   - FindRelatedWords -- knowledge graph connections
//
// Usage:
//   var kernel = Kernel.CreateBuilder()
//       .AddOpenAIChatCompletion("gpt-4o", apiKey)
//       .Build();
//   kernel.Plugins.AddFromType<WordOrbPlugin>();
//
// Requires: Microsoft.SemanticKernel (>= 1.0), System.Net.Http.Json
// =============================================================================

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.SemanticKernel;

namespace WordOrb.SemanticKernel;

/// <summary>
/// Semantic Kernel plugin that connects to the WordOrb.ai API.
/// Provides dictionary lookups, structured lessons, quizzes, and
/// knowledge-graph queries for vocabulary education.
/// </summary>
public sealed class WordOrbPlugin : IDisposable
{
    private readonly HttpClient _http;
    private readonly string _baseUrl;
    private readonly bool _ownsClient;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    // -------------------------------------------------------------------
    // Construction
    // -------------------------------------------------------------------

    /// <summary>
    /// Create a new WordOrbPlugin.
    /// </summary>
    /// <param name="apiKey">WordOrb API key (starts with wo_).</param>
    /// <param name="baseUrl">API base URL. Default: https://api.wordorb.ai</param>
    /// <param name="httpClient">Optional shared HttpClient. If null, one is created internally.</param>
    public WordOrbPlugin(
        string apiKey,
        string baseUrl = "https://api.wordorb.ai",
        HttpClient? httpClient = null)
    {
        if (string.IsNullOrWhiteSpace(apiKey))
            throw new ArgumentException(
                "apiKey is required. Get a free key at https://wordorb.ai/pricing",
                nameof(apiKey));

        _baseUrl = baseUrl.TrimEnd('/');

        if (httpClient is not null)
        {
            _http = httpClient;
            _ownsClient = false;
        }
        else
        {
            _http = new HttpClient();
            _ownsClient = true;
        }

        _http.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", apiKey);
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("semantic-kernel-wordorb/1.0.0");
        _http.DefaultRequestHeaders.Accept.ParseAdd("application/json");
    }

    // -------------------------------------------------------------------
    // Kernel Functions
    // -------------------------------------------------------------------

    /// <summary>
    /// Look up any English word in the WordOrb dictionary.
    /// Returns IPA pronunciation, definition, etymology, part of speech,
    /// example sentences, and translations in up to 47 languages.
    /// </summary>
    [KernelFunction("LookupWord")]
    [Description(
        "Look up any English word. Returns IPA pronunciation, definition, "
        "etymology, part of speech, and translations in 47 languages. "
        "Use when the user asks about a word's meaning, pronunciation, or origin.")]
    public async Task<string> LookupWordAsync(
        [Description("The English word to look up (e.g. 'courage', 'serendipity')")] string word,
        [Description("ISO 639-1 language code for translations (e.g. 'es', 'ja'). Optional.")] string? lang = null,
        CancellationToken ct = default)
    {
        var url = $"{_baseUrl}/api/word/{Uri.EscapeDataString(word)}";
        if (!string.IsNullOrEmpty(lang))
            url += $"?lang={Uri.EscapeDataString(lang)}";

        var data = await GetJsonAsync(url, ct);
        return FormatLookup(data);
    }

    /// <summary>
    /// Get a structured 5-phase vocabulary lesson.
    /// Phases: hook, story, wonder, action, wisdom.
    /// 365 days x 4 tracks x 3 age groups.
    /// </summary>
    [KernelFunction("GetLesson")]
    [Description(
        "Get a structured vocabulary lesson with 5 phases (hook, story, wonder, "
        "action, wisdom). Specify day (1-365), track (learn/grow/teach/trivia), "
        "and age group (kid/adult/elder). Use when building lesson plans or teaching.")]
    public async Task<string> GetLessonAsync(
        [Description("Day of the year (1-365). Each day has unique content.")] int day = 1,
        [Description("Learning track: learn, grow, teach, or trivia.")] string track = "learn",
        [Description("Age group: kid, adult, or elder.")] string ageGroup = "adult",
        CancellationToken ct = default)
    {
        var url = $"{_baseUrl}/api/lesson?day={day}&track={Uri.EscapeDataString(track)}" +
                  $"&age={Uri.EscapeDataString(ageGroup)}";

        var data = await GetJsonAsync(url, ct);
        return FormatLesson(data);
    }

    /// <summary>
    /// Get quiz questions aligned to a lesson or random from the question bank.
    /// Supports 6 question types: mc, tf, ab, open, reflection, quiz.
    /// </summary>
    [KernelFunction("GetQuiz")]
    [Description(
        "Get vocabulary quiz questions. Specify a day (1-365) for lesson-aligned "
        "questions, or set day to 0 for random questions. Filter by type: mc, tf, "
        "ab, open, reflection. Use when assessing vocabulary knowledge.")]
    public async Task<string> GetQuizAsync(
        [Description("Day of the year (1-365), or 0 for random questions.")] int day = 0,
        [Description("Learning track: learn, grow, teach, or trivia.")] string track = "learn",
        [Description("Question type filter: mc, tf, ab, open, reflection. Empty for all.")] string type = "",
        [Description("Number of random questions (1-20). Only used when day is 0.")] int count = 5,
        CancellationToken ct = default)
    {
        string url;
        if (day > 0)
        {
            url = $"{_baseUrl}/api/quiz?day={day}&track={Uri.EscapeDataString(track)}";
            if (!string.IsNullOrEmpty(type))
                url += $"&type={Uri.EscapeDataString(type)}";
        }
        else
        {
            url = $"{_baseUrl}/api/quiz/random?track={Uri.EscapeDataString(track)}" +
                  $"&count={Math.Min(count, 20)}";
            if (!string.IsNullOrEmpty(type))
                url += $"&type={Uri.EscapeDataString(type)}";
        }

        var data = await GetJsonAsync(url, ct);
        return FormatQuiz(data);
    }

    /// <summary>
    /// Query the knowledge graph to find all lessons where a word appears
    /// and discover related words across the 365-day curriculum.
    /// </summary>
    [KernelFunction("FindRelatedLessons")]
    [Description(
        "Query the knowledge graph for a word. Returns all lessons where the "
        "word appears, related words, and importance scores. Use to find "
        "thematic connections or build learning paths.")]
    public async Task<string> FindRelatedLessonsAsync(
        [Description("The word to search in the knowledge graph.")] string word,
        CancellationToken ct = default)
    {
        var url = $"{_baseUrl}/api/graph/word?word={Uri.EscapeDataString(word)}";
        var data = await GetJsonAsync(url, ct);
        return FormatGraph(data);
    }

    // -------------------------------------------------------------------
    // HTTP helper
    // -------------------------------------------------------------------

    private async Task<JsonElement> GetJsonAsync(string url, CancellationToken ct)
    {
        using var response = await _http.GetAsync(url, ct);

        if ((int)response.StatusCode == 429)
        {
            var retryAfter = response.Headers.RetryAfter?.Delta?.TotalSeconds ?? 60;
            throw new HttpRequestException(
                $"WordOrb rate limit exceeded. Retry after {retryAfter}s. " +
                "Upgrade at https://wordorb.ai/pricing");
        }

        if ((int)response.StatusCode == 401)
        {
            throw new HttpRequestException(
                "WordOrb authentication failed. Check your API key. " +
                "Get one at https://wordorb.ai/pricing");
        }

        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync(ct);
        return JsonSerializer.Deserialize<JsonElement>(json, JsonOpts);
    }

    // -------------------------------------------------------------------
    // Formatters
    // -------------------------------------------------------------------

    private static string FormatLookup(JsonElement data)
    {
        var parts = new List<string>
        {
            $"Word: {GetStr(data, "word")}"
        };

        if (TryGetStr(data, "ipa", out var ipa)) parts.Add($"IPA: {ipa}");
        if (TryGetStr(data, "pos", out var pos)) parts.Add($"Part of speech: {pos}");
        if (TryGetStr(data, "definition", out var def))
            parts.Add($"Definition: {def}");
        else if (TryGetStr(data, "def", out var def2))
            parts.Add($"Definition: {def2}");
        if (TryGetStr(data, "etymology", out var ety)) parts.Add($"Etymology: {ety}");
        if (TryGetStr(data, "example", out var ex)) parts.Add($"Example: {ex}");

        if (data.TryGetProperty("synonyms", out var syns) &&
            syns.ValueKind == JsonValueKind.Array)
        {
            var synList = syns.EnumerateArray().Select(s => s.GetString()).ToList();
            parts.Add($"Synonyms: {string.Join(", ", synList)}");
        }

        if (data.TryGetProperty("translations", out var tr) &&
            tr.ValueKind == JsonValueKind.Object)
        {
            var trLines = tr.EnumerateObject()
                .Take(5)
                .Select(p => $"  {p.Name}: {p.Value.GetString()}");
            parts.Add("Translations:\n" + string.Join("\n", trLines));
        }

        return string.Join("\n", parts);
    }

    private static string FormatLesson(JsonElement data)
    {
        var parts = new List<string>
        {
            $"Lesson: Day {GetStr(data, "day")} | Track: {GetStr(data, "track")} " +
            $"| Age: {GetStr(data, "age_group")}"
        };

        if (TryGetStr(data, "title", out var title)) parts.Add($"Title: {title}");
        if (TryGetStr(data, "theme", out var theme)) parts.Add($"Theme: {theme}");

        if (data.TryGetProperty("phases", out var phases) &&
            phases.ValueKind == JsonValueKind.Object)
        {
            foreach (var phaseName in new[] { "hook", "story", "wonder", "action", "wisdom" })
            {
                if (TryGetStr(phases, phaseName, out var content))
                    parts.Add($"\n--- {phaseName.ToUpperInvariant()} ---\n{content}");
            }
        }

        return string.Join("\n", parts);
    }

    private static string FormatQuiz(JsonElement data)
    {
        if (!data.TryGetProperty("interactions", out var interactions) ||
            interactions.ValueKind != JsonValueKind.Array ||
            interactions.GetArrayLength() == 0)
        {
            return "No quiz questions found for the given parameters.";
        }

        var parts = new List<string>
        {
            $"Quiz: {interactions.GetArrayLength()} question(s) | " +
            $"Track: {GetStr(data, "track")}"
        };

        int i = 1;
        foreach (var q in interactions.EnumerateArray())
        {
            parts.Add($"\nQ{i} [{GetStr(q, "type")}]: {GetStr(q, "prompt")}");

            if (q.TryGetProperty("choices", out var choices) &&
                choices.ValueKind == JsonValueKind.Array)
            {
                int idx = 0;
                foreach (var c in choices.EnumerateArray())
                {
                    parts.Add($"  {(char)(65 + idx)}. {c.GetString()}");
                    idx++;
                }
            }

            if (TryGetStr(q, "answer", out var ans))
                parts.Add($"  Answer: {ans}");
            if (TryGetStr(q, "explanation", out var exp))
                parts.Add($"  Explanation: {exp}");

            i++;
        }

        return string.Join("\n", parts);
    }

    private static string FormatGraph(JsonElement data)
    {
        var parts = new List<string>
        {
            $"Knowledge Graph: '{GetStr(data, "word")}' appears in " +
            $"{GetStr(data, "appears_in")} lesson(s)"
        };

        if (data.TryGetProperty("lessons", out var lessons) &&
            lessons.ValueKind == JsonValueKind.Array)
        {
            int count = 0;
            foreach (var lesson in lessons.EnumerateArray())
            {
                if (count++ >= 10) break;
                parts.Add(
                    $"  Day {GetStr(lesson, "day")} ({GetStr(lesson, "track")}) " +
                    $"- {GetStr(lesson, "phase")} phase, " +
                    $"importance={GetStr(lesson, "importance")}");
                if (TryGetStr(lesson, "context", out var ctx))
                    parts.Add($"    Context: {ctx}");
            }
        }

        if (data.TryGetProperty("related_words", out var related) &&
            related.ValueKind == JsonValueKind.Array)
        {
            var words = related.EnumerateArray().Select(w => w.GetString()).ToList();
            if (words.Count > 0)
                parts.Add($"\nRelated words: {string.Join(", ", words)}");
        }

        return string.Join("\n", parts);
    }

    // -------------------------------------------------------------------
    // JSON helpers
    // -------------------------------------------------------------------

    private static string GetStr(JsonElement el, string prop)
    {
        if (el.TryGetProperty(prop, out var val))
        {
            return val.ValueKind switch
            {
                JsonValueKind.String => val.GetString() ?? "",
                JsonValueKind.Number => val.GetRawText(),
                _ => val.GetRawText(),
            };
        }
        return "";
    }

    private static bool TryGetStr(JsonElement el, string prop, out string value)
    {
        value = GetStr(el, prop);
        return !string.IsNullOrEmpty(value);
    }

    // -------------------------------------------------------------------
    // IDisposable
    // -------------------------------------------------------------------

    public void Dispose()
    {
        if (_ownsClient)
            _http.Dispose();
    }
}
