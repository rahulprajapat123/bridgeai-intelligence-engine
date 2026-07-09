const ANALYZE_ENDPOINT = "/api/analyze-brief";
const DAILY_ENDPOINT = "/api/daily-intelligence/generate";

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return [...root.querySelectorAll(selector)];
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function titleize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function normalizeError(error) {
  if (error.status === 404) {
    return "This feature is not connected yet. Backend endpoint missing.";
  }
  if (error.businessMessage) return error.businessMessage;
  if (error.body && typeof error.body === "object" && error.body.detail) return String(error.body.detail);
  return "We could not complete the request. Please check the inputs and try again.";
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const error = new Error(typeof body === "string" ? body : body.detail || response.statusText);
    error.status = response.status;
    error.body = body;
    if (response.status === 404) {
      error.businessMessage = "This feature is not connected yet. Backend endpoint missing.";
    }
    throw error;
  }

  return body;
}

function setDebug(label, payload) {
  qs("#debug-output").textContent = `${label}\n\n${JSON.stringify(payload, null, 2)}`;
}

function setStatus(id, message, tone = "info") {
  const target = qs(id);
  target.textContent = message || "";
  target.className = `status-message ${tone}`;
}

function setLoading(form, isLoading, message, statusId) {
  const button = qs("button[type='submit']", form);
  button.disabled = isLoading;
  button.textContent = isLoading ? "Working..." : button.dataset.label;
  if (message) setStatus(statusId, message, isLoading ? "info" : "");
}

function startProgress(statusId, messages) {
  let index = 0;
  setStatus(statusId, messages[index], "info");
  return window.setInterval(() => {
    index = Math.min(index + 1, messages.length - 1);
    setStatus(statusId, messages[index], "info");
  }, 1200);
}

function emptyMessage(message) {
  return `<div class="card-body empty">${escapeHtml(message)}</div>`;
}

function asArray(value) {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function renderValue(value) {
  if (value === null || value === undefined || value === "") return `<div class="empty small">No information available yet.</div>`;
  if (Array.isArray(value)) return renderList(value);
  if (typeof value === "object") return renderObject(value);
  return `<p>${escapeHtml(value)}</p>`;
}

function renderList(items) {
  if (!items.length) return `<div class="empty small">No information available yet.</div>`;
  return `<ul class="clean-list">${items.map((item) => `<li>${renderInline(item)}</li>`).join("")}</ul>`;
}

function renderInline(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") {
    const title = value.title || value.name || value.technology_name || value.source || value.claim_text || "Item";
    const description = value.summary || value.description || value.key_findings || value.implementation_guidance || value.evidence_summary || "";
    const url = value.url || value.source_url || value.html_url || value.link;
    return `${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>` : `<strong>${escapeHtml(title)}</strong>`}${description ? `<p>${escapeHtml(description)}</p>` : ""}`;
  }
  return escapeHtml(value);
}

function renderObject(value) {
  const rows = Object.entries(value).filter(([, item]) => item !== null && item !== undefined && item !== "");
  if (!rows.length) return `<div class="empty small">No information available yet.</div>`;
  return `<dl class="definition-list">${rows.map(([key, item]) => `<div><dt>${escapeHtml(titleize(key))}</dt><dd>${renderValue(item)}</dd></div>`).join("")}</dl>`;
}

function renderSources(items) {
  const sources = asArray(items).filter(Boolean);
  if (!sources.length) return `<div class="empty small">No sources returned yet.</div>`;
  return sources
    .map((item, index) => {
      const title = item.title || item.name || item.source || item.source_name || `Source ${index + 1}`;
      const url = item.url || item.source_url || item.link || item.html_url;
      const sourceType = item.source_type || item.type || item.source || "";
      const summary = item.summary || item.key_findings || item.evidence_summary || item.description || item.claim_text || "";
      return `
        <details class="source-card">
          <summary>
            <span>${escapeHtml(title)}</span>
            ${sourceType ? `<small>${escapeHtml(sourceType)}</small>` : ""}
          </summary>
          ${summary ? `<p>${escapeHtml(summary)}</p>` : ""}
          ${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">Open source</a>` : ""}
        </details>
      `;
    })
    .join("");
}

function renderTable(rows) {
  const data = asArray(rows).filter((row) => row && typeof row === "object");
  if (!data.length) return `<div class="empty small">No table rows returned yet.</div>`;
  const columns = [...new Set(data.flatMap((row) => Object.keys(row)))].slice(0, 6);
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>${columns.map((column) => `<th>${escapeHtml(titleize(column))}</th>`).join("")}</tr></thead>
        <tbody>
          ${data
            .map((row) => `<tr>${columns.map((column) => `<td>${renderCell(row[column])}</td>`).join("")}</tr>`)
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderCell(value) {
  if (Array.isArray(value)) return escapeHtml(value.join(", "));
  if (value && typeof value === "object") return escapeHtml(value.title || value.name || JSON.stringify(value));
  return escapeHtml(value ?? "");
}

function setCard(containerId, cardName, content, renderer = renderValue) {
  const card = qs(`${containerId} [data-card="${cardName}"] .card-body`);
  if (!card) return;
  card.innerHTML = renderer(content);
  card.dataset.copyText = textFromContent(content);
}

function textFromContent(content) {
  if (content === null || content === undefined) return "";
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content.map((item) => (typeof item === "string" ? item : JSON.stringify(item, null, 2))).join("\n\n");
  }
  return JSON.stringify(content, null, 2);
}

function pick(data, keys, fallback = null) {
  for (const key of keys) {
    if (data && data[key] !== undefined && data[key] !== null) return data[key];
  }
  return fallback;
}

function renderAnalyze(data) {
  const understanding = data.brief_understanding || data.analysis || data.brief_analysis || data;
  const solution = data.solution || {};
  const evidence = data.evidence || {};
  const papers = evidence.papers || data.similar_papers || data.papers || [];
  const repos = evidence.github_repositories || data.github_repositories || data.repositories || [];
  const blogsNews = [
    ...(evidence.blogs || []),
    ...(evidence.news || []),
    ...(evidence.industry_sources || []),
    ...(data.blogs_articles_news || []),
  ];
  const sourceTable = data.source_table || data.evidence_table || [];

  setCard("#analyze-output", "brief_understanding", {
    title: understanding.title,
    summary: understanding.summary,
    objective: understanding.objective,
    problem_statement: understanding.problem_statement,
    domain: understanding.domain,
    intent: understanding.intent,
  });
  setCard("#analyze-output", "extracted_requirements", {
    requirements: understanding.requirements || [],
    constraints: understanding.constraints || [],
    deliverables: understanding.deliverables || [],
    success_criteria: understanding.success_criteria || [],
  });
  setCard("#analyze-output", "recommended_solution", {
    recommended_approach: solution.recommended_approach,
    why_this_approach: solution.why_this_approach,
    cost_estimate: solution.cost_estimate,
    alternatives: solution.alternatives,
  });
  setCard("#analyze-output", "architecture", solution.architecture);
  setCard("#analyze-output", "tools_technologies", {
    tools_and_technologies: solution.tools_and_technologies || [],
    apis_required: solution.apis_required || [],
  });
  setCard("#analyze-output", "implementation_plan", {
    implementation_steps: solution.implementation_steps || [],
    timeline: solution.timeline || [],
  });
  setCard("#analyze-output", "risks_mitigations", solution.risks_and_mitigations || []);
  setCard("#analyze-output", "similar_papers", papers, renderSources);
  setCard("#analyze-output", "github_repositories", repos, renderSources);
  setCard("#analyze-output", "blogs_articles_news", blogsNews, renderSources);
  setCard("#analyze-output", "evidence_table", sourceTable, renderTable);
  setCard("#analyze-output", "warnings", data.warnings || []);
}

function renderDaily(data) {
  const report = data.report || data;
  const emailStatus = report.email_status || (data.sent ? { sent: true, message: "Email sent." } : { sent: false, message: "Generated. Email not sent." });

  setCard("#daily-output", "executive_summary", pick(report, ["executive_summary", "summary", "overview"], []));
  setCard("#daily-output", "top_developments", pick(report, ["top_developments", "developments", "highlights"], []));
  setCard("#daily-output", "marketing_ai", pick(report, ["marketing_ai", "ai_in_marketing"], []));
  setCard("#daily-output", "sales_ai", pick(report, ["sales_ai", "ai_in_sales"], []));
  setCard("#daily-output", "insights_analytics", pick(report, ["insights_analytics", "analytics", "ai_in_insights_and_analytics"], []));
  setCard("#daily-output", "agentic_llm_rag", pick(report, ["agentic_llm_rag", "agentic_ai_llm_rag", "agentic_ai"], []));
  setCard("#daily-output", "important_papers", pick(report, ["important_papers", "papers", "research_papers"], []), renderSources);
  setCard("#daily-output", "useful_github_repositories", pick(report, ["useful_github_repositories", "github_repositories", "repositories"], []), renderSources);
  setCard("#daily-output", "newsletter_angles", pick(report, ["newsletter_angles", "angles"], []));
  setCard("#daily-output", "newsletter_draft", pick(report, ["newsletter_draft", "draft", "newsletter"], ""));
  setCard("#daily-output", "source_table", pick(report, ["source_table", "sources", "citations"], []), renderTable);
  setCard("#daily-output", "email_status", emailStatus);
  setCard("#daily-output", "daily_warnings", report.warnings || []);
}

function showBusinessError(containerId, message) {
  const firstCard = qs(`${containerId} .result-card .card-body`);
  if (firstCard) {
    firstCard.innerHTML = `<div class="notice error">${escapeHtml(message)}</div>`;
  }
}

// Wait for DOM to be fully loaded before attaching event listeners
document.addEventListener("DOMContentLoaded", () => {
  qsa(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      const tab = button.dataset.tab;
      qsa(".tab").forEach((item) => item.classList.toggle("is-active", item === button));
      qsa(".view").forEach((view) => view.classList.toggle("is-visible", view.id === `view-${tab}`));
    });
  });

  qsa("button[type='submit']").forEach((button) => {
    button.dataset.label = button.textContent;
  });

  qsa(".copy-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest(".result-card");
      const body = qs(".card-body", card);
      const text = body.dataset.copyText || body.textContent.trim();
      if (!text) return;
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
      setTimeout(() => {
        button.textContent = "Copy";
      }, 1400);
    });
  });

  const analyzeForm = qs("#analyze-form");
  if (analyzeForm) {
    analyzeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const file = qs("#brief-file").files[0];
  const briefText = qs("#brief-text").value.trim();

  if (!file && briefText.length < 20) {
    setStatus("#analyze-status", "Please upload a brief or paste at least 20 characters.", "error");
    return;
  }

  const formData = new FormData();
  if (file) formData.append("file", file);
  formData.append("brief_text", briefText);
  formData.append("domain_override", String(qs("#domain").value || "").trim());
  formData.append("top_k", String(Number(qs("#top-k").value || 10)));
  formData.append("include_papers", qs("[name='include_papers']").checked ? "true" : "false");
  formData.append("include_github", qs("[name='include_github']").checked ? "true" : "false");
  formData.append("include_blogs", qs("[name='include_blogs']").checked ? "true" : "false");
  formData.append("include_news", qs("[name='include_news']").checked ? "true" : "false");

  setLoading(form, true, "Analyzing brief and collecting evidence...", "#analyze-status");
  const progress = startProgress("#analyze-status", [
    "Analyzing brief...",
    "Understanding requirements...",
    "Searching papers...",
    "Searching GitHub...",
    "Searching blogs and news...",
    "Ranking evidence...",
    "Preparing implementation plan...",
  ]);
  try {
    const data = await request(ANALYZE_ENDPOINT, { method: "POST", body: formData });
    renderAnalyze(data);
    setDebug("Analyze Brief response", data);
    setStatus("#analyze-status", "Analysis complete.", "success");
  } catch (error) {
    const message = normalizeError(error);
    showBusinessError("#analyze-output", message);
    setDebug("Analyze Brief error", { status: error.status, message: error.message, body: error.body });
    setStatus("#analyze-status", message, "error");
  } finally {
    window.clearInterval(progress);
    setLoading(form, false, "", "#analyze-status");
  }
    });
  }

  const dailyForm = qs("#daily-form");
  if (dailyForm) {
    dailyForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      const topics = formData.getAll("topics");
      const payload = {
        recipient_email: String(formData.get("recipient") || "").trim() || null,
        max_items: Number(formData.get("max_items") || 20),
        send_email: Boolean(formData.get("send_email")),
        topics,
      };

      setLoading(form, true, "Generating the daily intelligence report...", "#daily-status");
      const progress = startProgress("#daily-status", [
        "Fetching latest AI developments...",
        "Searching news and blogs...",
        "Searching papers...",
        "Searching GitHub repositories...",
        "Ranking business relevance...",
        "Preparing newsletter draft...",
        payload.send_email ? "Sending email if selected..." : "Finalizing report...",
      ]);
      try {
        const data = await request(DAILY_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        renderDaily(data);
        setDebug("Daily Intelligence response", data);
        setStatus("#daily-status", "Report generated.", "success");
      } catch (error) {
        const message = normalizeError(error);
        showBusinessError("#daily-output", message);
        setDebug("Daily Intelligence error", { status: error.status, message: error.message, body: error.body });
        setStatus("#daily-status", message, "error");
      } finally {
        window.clearInterval(progress);
        setLoading(form, false, "", "#daily-status");
      }
    });
  }
});
