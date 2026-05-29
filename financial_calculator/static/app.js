const form = document.querySelector("#calculator-form");
const result = document.querySelector("#result");
const roundedResult = document.querySelector("#rounded-result");
const resultsBlock = document.querySelector(".results");
const numberInputs = document.querySelectorAll('input[type="text"]');

function showResults(mainText, roundedText = "", isError = false) {
  result.textContent = mainText;
  roundedResult.textContent = roundedText;
  resultsBlock.classList.toggle("error", isError);
}

function normalizeTypedValue(value) {
  return value.replace(/[^\d+\-., \u00a0]/g, "");
}

numberInputs.forEach((input) => {
  input.addEventListener("input", () => {
    const normalized = normalizeTypedValue(input.value);
    if (input.value !== normalized) {
      const cursor = input.selectionStart ?? normalized.length;
      input.value = normalized;
      const nextCursor = Math.max(0, Math.min(normalized.length, cursor - 1));
      input.setSelectionRange(nextCursor, nextCursor);
    }
  });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const payload = {
    operands: [
      formData.get("number1") ?? "",
      formData.get("number2") ?? "",
      formData.get("number3") ?? "",
      formData.get("number4") ?? "",
    ],
    operations: [
      formData.get("operation1") ?? "+",
      formData.get("operation2") ?? "+",
      formData.get("operation3") ?? "+",
    ],
    rounding: document.querySelector('input[name="rounding"]:checked')?.value ?? "math",
  };

  try {
    const response = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!response.ok || !data.ok) {
      showResults(data.error || "Не удалось выполнить расчет.", "", true);
      return;
    }

    showResults(data.result, data.rounded);
  } catch (_error) {
    showResults("Сервер недоступен. Перезапустите приложение.", "", true);
  }
});

document.querySelectorAll('input[name="rounding"]').forEach((input) => {
  input.addEventListener("change", () => form.requestSubmit());
});
