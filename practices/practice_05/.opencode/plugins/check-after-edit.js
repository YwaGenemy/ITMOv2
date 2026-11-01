// Hook: после каждой правки файла запускает sh scripts/check.sh и возвращает результат агенту.
// OpenCode 1.x: событие tool.execute.after, вывод инструмента можно дополнить.
import { appendFile } from "node:fs/promises"

const EDIT_TOOLS = new Set(["edit", "write", "patch", "multiedit", "apply_patch"])
const TAIL_LINES = 40

export const CheckAfterEdit = async ({ $, directory }) => ({
  "tool.execute.after": async (input, output) => {
    if (!EDIT_TOOLS.has(input.tool)) return

    const run = await $`sh scripts/check.sh`.cwd(directory).nothrow().quiet()
    const verdict = run.exitCode === 0 ? "PASS" : "FAIL"
    const text = (run.stdout.toString() + run.stderr.toString()).trim()
    const tail = text.split("\n").slice(-TAIL_LINES).join("\n")

    output.output += `\n\n[check-after-edit] sh scripts/check.sh → ${verdict}\n${tail}`
    if (verdict === "FAIL") {
      output.output += "\n[check-after-edit] Исправь причину сбоя, не ослабляя проверку."
    }

    const line = `${new Date().toISOString()} ${input.tool} ${verdict} ${tail.split("\n").at(-1)}\n`
    await appendFile(`${directory}/evidence/hook.log`, line).catch(() => {})
  },
})
