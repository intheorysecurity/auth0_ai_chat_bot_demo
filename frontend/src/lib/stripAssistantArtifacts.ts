/**
 * Remove model "thinking" blocks and collapsed junk from streamed assistant text.
 * Run once when a turn finishes (onDone), not per-token (tags may split across chunks).
 */
export function stripAssistantArtifacts(text: string): string {
  let t = text;
  // Fenced "think" / reasoning blocks (common in some local models)
  t = t.replace(/```\s*think\s*[\s\S]*?```/gi, "");
  t = t.replace(/```\s*redacted_reasoning\s*[\s\S]*?```/gi, "");
  // Single-backtick XML-ish: `think` ... `</think>`
  t = t.replace(/`think`[\s\S]*?`\/think`/gi, "");
  t = t.replace(/<thinking>[\s\S]*?<\/thinking>/gi, "");
  t = t.replace(/<reasoning>[\s\S]*?<\/reasoning>/gi, "");
  // Collapse excessive blank lines from broken streams
  t = t.replace(/\n{4,}/g, "\n\n");
  return t.trim();
}

/** Simple "show my orders" style questions without cancel/buy side quests. */
export function userWantsOrdersListOnly(content: string): boolean {
  const n = content.trim().toLowerCase();
  if (n.length > 280) return false;
  const orderIntent =
    /\b(my orders|show\s+(me\s+)?(my\s+)?orders|list\s+(my\s+)?orders|what orders|orders\s+(do\s+i|have\s+i)|order history|past orders)\b/.test(
      n
    );
  if (!orderIntent) return false;
  const skip =
    /\b(cancel|delete|buy|purchase|create\s+order|permission|who\s*am\s*i|check\s+permission|product\s+catalog)\b/.test(
      n
    );
  return !skip;
}
