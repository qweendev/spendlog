const telegram = window.Telegram?.WebApp;

const WORDS = {
  en: { empty: "No expenses this month.", confirm: "Delete this expense?", today: "Today", yesterday: "Yesterday" },
  ru: { empty: "В этом месяце трат нет.", confirm: "Удалить эту трату?", today: "Сегодня", yesterday: "Вчера" },
};

const OUTSIDE_TELEGRAM = "Open this page from the bot in Telegram.";
const CIRCUMFERENCE = 2 * Math.PI * 48;

const view = {
  app: document.querySelector(".app"),
  notice: document.querySelector(".notice"),
  title: document.querySelector(".month__title"),
  steps: document.querySelectorAll(".month__step"),
  total: document.querySelector(".total__amount"),
  donut: document.querySelector(".donut"),
  legend: document.querySelector(".legend"),
  bars: document.querySelector(".bars"),
  history: document.querySelector(".history"),
  row: document.querySelector("#expense-row"),
};

let shownMonth = null;
let currentMonth = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", Authorization: `tma ${telegram.initData}`, ...options.headers },
  });
  if (!response.ok) throw new Error(`${options.method ?? "GET"} ${path}: ${response.status}`);
  return response.status === 204 ? null : response.json();
}

function formatter(summary) {
  const whole = new Intl.NumberFormat(summary.lang, { style: "currency", currency: summary.currency, maximumFractionDigits: 0 });
  const exact = new Intl.NumberFormat(summary.lang, { style: "currency", currency: summary.currency });
  return (minor) => (minor % 100 === 0 ? whole : exact).format(minor / 100);
}

function shiftMonth(month, step) {
  const [year, index] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year, index - 1 + step, 1));
  return date.toISOString().slice(0, 7);
}

function svg(tag, attributes) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
}

function categoryColor(key) {
  return `var(--c-${key})`;
}

function drawDonut(summary) {
  view.donut.replaceChildren(svg("circle", { cx: 60, cy: 60, r: 48, stroke: "var(--surface)" }));
  let offset = 0;
  for (const category of summary.categories) {
    const length = (category.amount / summary.total) * CIRCUMFERENCE;
    view.donut.append(svg("circle", {
      cx: 60, cy: 60, r: 48,
      stroke: categoryColor(category.key),
      "stroke-dasharray": `${Math.max(length - 1.5, 0.5)} ${CIRCUMFERENCE}`,
      "stroke-dashoffset": -offset,
    }));
    offset += length;
  }
}

function drawLegend(summary, money) {
  view.legend.hidden = summary.categories.length === 0;
  view.legend.replaceChildren(...summary.categories.map((category) => {
    const item = document.createElement("li");
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.setProperty("--dot", categoryColor(category.key));
    const label = document.createElement("span");
    label.textContent = category.label;
    const share = document.createElement("span");
    share.className = "legend__share";
    share.textContent = `${Math.round((category.amount / summary.total) * 100)}%`;
    const amount = document.createElement("span");
    amount.className = "legend__amount";
    amount.textContent = money(category.amount);
    item.append(dot, label, share, amount);
    return item;
  }));
}

function drawBars(summary) {
  const width = 100;
  const height = 72;
  const gap = 0.8;
  const slot = width / summary.days.length;
  const peak = Math.max(...summary.days.map((day) => day.amount), 1);
  const today = new Date().toLocaleDateString("sv");
  view.bars.setAttribute("viewBox", `0 0 ${width} ${height}`);
  view.bars.replaceChildren(...summary.days.map((day, index) => {
    const barHeight = day.amount ? Math.max((day.amount / peak) * height, 3) : 2;
    const bar = svg("rect", {
      x: index * slot + gap / 2,
      y: height - barHeight,
      width: slot - gap,
      height: barHeight,
      rx: 0.8,
    });
    bar.classList.toggle("is-spent", day.amount > 0);
    bar.classList.toggle("is-today", day.date === today);
    return bar;
  }));
}

function dayLabel(isoDate, lang) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (isoDate === today.toLocaleDateString("sv")) return WORDS[lang].today;
  if (isoDate === yesterday.toLocaleDateString("sv")) return WORDS[lang].yesterday;
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString(lang, { day: "numeric", month: "long", weekday: "short" });
}

function drawHistory(summary, money) {
  if (summary.expenses.length === 0) {
    const empty = document.createElement("p");
    empty.className = "notice";
    empty.textContent = WORDS[summary.lang].empty;
    view.history.replaceChildren(empty);
    return;
  }
  const groups = Map.groupBy(summary.expenses, (expense) => expense.created_at.slice(0, 10));
  view.history.replaceChildren(...[...groups].flatMap(([isoDate, expenses]) => {
    const heading = document.createElement("h2");
    heading.textContent = dayLabel(isoDate, summary.lang);
    const list = document.createElement("ul");
    list.append(...expenses.map((expense) => expenseRow(expense, summary, money)));
    return [heading, list];
  }));
}

function expenseRow(expense, summary, money) {
  const row = view.row.content.firstElementChild.cloneNode(true);
  row.querySelector(".expense__dot").style.setProperty("--dot", categoryColor(expense.category));
  row.querySelector(".expense__note").textContent = expense.note || expense.label;
  row.querySelector(".expense__meta").textContent = expense.note
    ? `${expense.label}, ${expense.created_at.slice(11, 16)}`
    : expense.created_at.slice(11, 16);
  row.querySelector(".expense__amount").textContent = money(expense.amount);
  row.querySelector(".expense__delete").addEventListener("click", () => {
    telegram.showConfirm(WORDS[summary.lang].confirm, async (confirmed) => {
      if (!confirmed) return;
      await api(`/api/expenses/${expense.id}`, { method: "DELETE" });
      telegram.HapticFeedback.notificationOccurred("success");
      await show(shownMonth);
    });
  });
  return row;
}

async function show(month) {
  const summary = await api(month ? `/api/summary?month=${month}` : "/api/summary");
  shownMonth = summary.month;
  currentMonth ??= summary.month;
  const money = formatter(summary);

  document.documentElement.lang = summary.lang;
  view.title.textContent = summary.title;
  view.total.textContent = money(summary.total);
  view.steps[1].disabled = shownMonth >= currentMonth;
  drawDonut(summary);
  drawLegend(summary, money);
  drawBars(summary);
  drawHistory(summary, money);
  view.app.hidden = false;
}

async function start() {
  if (!telegram?.initData) {
    view.notice.textContent = OUTSIDE_TELEGRAM;
    view.notice.hidden = false;
    return;
  }
  telegram.ready();
  telegram.expand();

  for (const button of view.steps) {
    button.addEventListener("click", async () => {
      telegram.HapticFeedback.selectionChanged();
      await show(shiftMonth(shownMonth, Number(button.dataset.step)));
    });
  }

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  await api("/api/me/timezone", { method: "PUT", body: JSON.stringify({ timezone }) }).catch(() => {});
  await show(null);
}

start().catch((error) => {
  console.error(error);
  view.notice.textContent = error.message;
  view.notice.hidden = false;
});
