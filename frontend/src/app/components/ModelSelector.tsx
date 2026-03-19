"use client";

interface ModelSelectorProps {
  model: string;
  onModelChange: (model: string) => void;
}

const MODELS = [
  { value: "claude", label: "Claude" },
  { value: "openai", label: "OpenAI" },
  { value: "ollama", label: "Ollama" },
];

export default function ModelSelector({
  model,
  onModelChange,
}: ModelSelectorProps) {
  return (
    <select
      value={model}
      onChange={(e) => onModelChange(e.target.value)}
      className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {MODELS.map((m) => (
        <option key={m.value} value={m.value}>
          {m.label}
        </option>
      ))}
    </select>
  );
}
