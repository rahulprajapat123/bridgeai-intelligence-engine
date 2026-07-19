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
  if (error.status === 409) {
    // Handle conflict errors with specific messaging
    const message = error.body && typeof error.body === "object" && error.body.detail 
      ? error.body.detail 
      : "Conflict: Unable to complete this action.";
    
    // Make it more user-friendly if it's about pending items
    if (message.includes("items still require a review decision")) {
      return `⚠️ ${message}\n\nThis should not happen with auto-approval enabled. Try refreshing the page and clicking Submit Review again. If the issue persists, some items may be missing summaries.`;
    }
    if (message.includes("already locked")) {
      return "This batch has already been submitted and locked. Select a different batch to continue reviewing.";
    }
    return message;
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

async function downloadPdf(url, button, fallbackName, statusSelector = "#daily-status") {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Building PDF...";
  try {
    const response = await fetch(url, {headers: {Accept: "application/pdf"}});
    if (!response.ok) throw new Error(await response.text() || `PDF export failed (${response.status})`);
    const blob = await response.blob();
    if (blob.type !== "application/pdf" || blob.size < 1000) {
      throw new Error("The server returned an empty or invalid PDF.");
    }
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = match?.[1] || fallbackName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    setStatus(statusSelector, `Downloaded ${blob.size.toLocaleString()} bytes of report data.`, "success");
  } catch (error) {
    setStatus(statusSelector, error.message || normalizeError(error), "error");
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
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

function renderRecommendations(rows) {
  const recommendations = asArray(rows);
  if (!recommendations.length) return `<div class="empty small">No evidence-backed recommendations returned.</div>`;
  return recommendations.map((item, index) => `
    <article class="source-card">
      <h4>${index + 1}. ${escapeHtml(item.recommendation || "Recommendation")}</h4>
      <p>${escapeHtml(item.reasoning || "")}</p>
      <small>Confidence: ${escapeHtml(item.confidence_score ?? "N/A")}</small>
      <div class="citation-row">${asArray(item.supporting_sources).filter(Boolean).map((url, sourceIndex) =>
        `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Source ${sourceIndex + 1}</a>`
      ).join("")}</div>
    </article>
  `).join("");
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
    data_inputs: understanding.data_inputs || understanding.inputs || [],
    integrations: understanding.integrations || [],
    governance_requirements: understanding.governance_requirements || [],
    evaluation_requirements: understanding.evaluation_requirements || [],
    decisions_to_make: understanding.decisions_to_make || [],
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
  setCard("#analyze-output", "ranked_recommendations", data.ranked_recommendations || [], renderRecommendations);
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

// Daily Intelligence v2 is intentionally isolated from Analyze Brief.
document.addEventListener("DOMContentLoaded", () => {
  const runButton = qs("#daily-run");
  if (!runButton) return;
  const state = { batchId: "", sourceType: "academic", page: 1, pages: 1, selected: new Set(), items: new Map(), editing: null };

  async function loadBatches(selectNewest = false) {
    const batches = await request("/api/daily-intelligence/batches");
    const select = qs("#daily-batch");
    select.innerHTML = batches.length ? batches.map((b) => `<option value="${escapeHtml(b.id)}">${escapeHtml(new Date(b.created_at).toLocaleString())} - ${escapeHtml(b.status)}</option>`).join("") : `<option value="">No batches yet</option>`;
    if (selectNewest && batches.length) state.batchId = batches[0].id;
    if (!state.batchId && batches.length) state.batchId = batches[0].id;
    select.value = state.batchId;
    if (state.batchId) await loadBatch();
  }

  async function autoApprovePending() {
    try {
      // Fetch ALL pending items using pagination (max 100 per page)
      let allPendingSummaries = [];
      let page = 1;
      let hasMore = true;
      
      setStatus("#daily-status", `🔍 Scanning for pending items... (page ${page})`, "info");
      
      while (hasMore) {
        const items = await request(`/api/daily-intelligence/batches/${state.batchId}/items?page=${page}&page_size=100&review_status=pending`);
        const pendingSummaries = items.items.filter(item => item.summary?.id).map(item => item.summary.id);
        allPendingSummaries.push(...pendingSummaries);
        
        // Check if there are more pages
        hasMore = items.items.length === 100;
        page++;
        
        // Show scanning progress
        if (hasMore) {
          setStatus("#daily-status", `🔍 Scanning for pending items... (page ${page}, found ${allPendingSummaries.length} so far)`, "info");
        }
        
        // Safety limit to prevent infinite loops
        if (page > 50) break;
      }
      
      if (allPendingSummaries.length === 0) {
        return 0;
      }
      
      // Bulk-review has max 500 items per request, so batch them
      const batchSize = 500;
      let approvedCount = 0;
      const totalItems = allPendingSummaries.length;
      
      for (let i = 0; i < allPendingSummaries.length; i += batchSize) {
        const batch = allPendingSummaries.slice(i, i + batchSize);
        
        // Show percentage before request
        const percentage = Math.round((approvedCount / totalItems) * 100);
        setStatus("#daily-status", `⏳ Auto-approving... ${approvedCount}/${totalItems} (${percentage}%)`, "info");
        
        await request("/api/daily-intelligence/summaries/bulk-review", {
          method: "POST", 
          headers: {"Content-Type": "application/json"}, 
          body: JSON.stringify({summary_ids: batch, action: "approve"})
        });
        
        approvedCount += batch.length;
        
        // Show updated percentage after completion
        const newPercentage = Math.round((approvedCount / totalItems) * 100);
        setStatus("#daily-status", `⏳ Auto-approving... ${approvedCount}/${totalItems} (${newPercentage}%)`, "info");
      }
      
      setStatus("#daily-status", `✓ Auto-approved ${approvedCount} items (100%). Review and reject any that don't meet standards.`, "success");
      return approvedCount;
    } catch (e) {
      const errorMsg = e.body?.detail || e.message || String(e);
      setStatus("#daily-status", `Auto-approval failed: ${errorMsg}. Try using "Approve All Pending" button or check console for details.`, "error");
      console.error("Auto-approval error:", e);
      throw e;
    }
  }

  async function loadBatch() {
    const batch = await request(`/api/daily-intelligence/batches/${state.batchId}`);
    qs("#daily-batch-status").textContent = `${batch.status} - ${batch.unique_items} unique / ${batch.total_raw_items} fetched`;
    renderHealth(batch.source_runs || []);
    
    // Auto-approve all pending items when batch is ready for review (trust by default)
    if (batch.status === "awaiting_review") {
      try {
        await autoApprovePending();
      } catch (e) {
        console.warn("Auto-approve failed:", e);
      }
    }
    
    await loadItems();
    if (["created", "ingesting", "summarizing"].includes(batch.status)) setTimeout(() => loadBatches(true).catch(showError), 2500);
  }

  async function loadItems() {
    const params = new URLSearchParams({source_type: state.sourceType, page: state.page, page_size: 20});
    const data = await request(`/api/daily-intelligence/batches/${state.batchId}/items?${params}`);
    state.pages = Math.max(1, Math.ceil(data.total / data.page_size)); state.items.clear(); data.items.forEach((x) => state.items.set(x.id, x));
    qs("#daily-page").textContent = `Page ${state.page} of ${state.pages}`;
    const counts = data.items.reduce((out, item) => { out[item.review_status] = (out[item.review_status] || 0) + 1; return out; }, {});
    qs("#source-overview").innerHTML = `<strong>${titleize(state.sourceType)}</strong><span>${data.total} unique items</span><span>${counts.rejected || 0} rejected</span><span>${data.total - (counts.rejected || 0)} will be published</span>`;
    qs("#daily-items").innerHTML = data.items.length ? data.items.map(renderReviewItem).join("") : `<div class="panel empty">No ${escapeHtml(state.sourceType)} items available.</div>`;
    bindItemActions();
  }

  function renderReviewItem(item) {
    const summary = item.summary || {}; const structured = summary.structured_summary || {}; const citations = summary.citations || [];
    const isRejected = item.review_status === 'rejected';
    const cardClass = isRejected ? 'panel review-card rejected-item' : 'panel review-card';
    return `<article class="${cardClass}"><div class="review-card-head"><label><input class="item-select" type="checkbox" data-summary-id="${escapeHtml(summary.id || "")}" ${isRejected ? '' : ''}/> ${isRejected ? '<span class="status-pill" style="background: #dc3545;">Rejected</span>' : '<span class="status-pill" style="background: #28a745;">✓ Approved</span>'}</label><span>${escapeHtml(item.source_name)} / ${escapeHtml(item.source_type)}</span></div><h3>${escapeHtml(item.title)}</h3><div class="item-meta"><span>${item.publication_date ? escapeHtml(new Date(item.publication_date).toLocaleDateString()) : "Date unknown"}</span><span>Relevance ${item.relevance_score}</span><span>Credibility ${item.credibility_score}</span><span>Confidence ${Math.round((structured.confidence_score || 0) * 100)}%</span></div><p>${escapeHtml(summary.display_summary_text || "Summary pending")}</p>${renderList(structured.key_findings || [])}<div class="citation-row">${citations.map((c) => `<a href="${escapeHtml(c.source_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(c.source_name || "Citation")}</a>`).join("")}</div><div class="review-actions">${isRejected ? '<button data-action="approve" data-summary-id="' + escapeHtml(summary.id || "") + '" style="background: #28a745;">Undo Reject</button>' : '<button data-action="reject" data-summary-id="' + escapeHtml(summary.id || "") + '" style="background: #dc3545; color: white;">Reject</button>'}<button data-action="edit" data-item-id="${escapeHtml(item.id)}">Edit</button><a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">View Source</a></div></article>`;
  }

  function bindItemActions() {
    qsa(".item-select").forEach((box) => box.addEventListener("change", () => box.checked ? state.selected.add(box.dataset.summaryId) : state.selected.delete(box.dataset.summaryId)));
    qsa("[data-action='approve']").forEach((button) => button.addEventListener("click", async () => { await request(`/api/daily-intelligence/summaries/${button.dataset.summaryId}/approve`, {method: "POST"}); await loadItems(); }));
    qsa("[data-action='reject']").forEach((button) => button.addEventListener("click", async () => { await request(`/api/daily-intelligence/summaries/${button.dataset.summaryId}/reject`, {method: "POST"}); await loadItems(); }));
    qsa("[data-action='edit']").forEach((button) => button.addEventListener("click", () => openEditor(state.items.get(button.dataset.itemId))));
  }

  function openEditor(item) {
    state.editing = item; qs("#dialog-title").textContent = item.title; qs("#dialog-summary").value = item.summary.display_summary_text || ""; qs("#dialog-notes").value = item.summary.reviewer_notes || ""; qs("#dialog-raw").textContent = JSON.stringify({raw_content: item.raw_content, metadata: item.metadata}, null, 2); qs("#summary-dialog").showModal();
  }

  async function bulkReject() {
    if (!state.selected.size) return setStatus("#daily-status", "Select at least one item to reject.", "error");
    await request("/api/daily-intelligence/summaries/bulk-review", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({summary_ids: [...state.selected], action: "reject"})}); state.selected.clear(); await loadItems();
  }
  function renderHealth(rows) { qs("#source-health").innerHTML = rows.length ? rows.map((x) => `<div class="health-item"><strong>${escapeHtml(x.source_name)}</strong><span class="health-${escapeHtml(x.status)}">${escapeHtml(x.status === "no_results" ? "no matching items" : x.status)}</span><small>${x.items_returned} items / ${x.response_time_ms} ms</small>${x.error ? `<small>${escapeHtml(x.error)}</small>` : ""}</div>`).join("") : `<div class="empty">No source checks yet.</div>`; }
  function showError(error) { setStatus("#daily-status", normalizeError(error), "error"); }

  runButton.addEventListener("click", async () => { try { setStatus("#daily-status", "Queueing ingestion...", "info"); const result = await request("/api/daily-intelligence/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"}); state.batchId = result.batch_id; await loadBatches(true); } catch (e) { showError(e); } });
  
  const dailyBatch = qs("#daily-batch");
  const dailyPrev = qs("#daily-prev");
  const dailyNext = qs("#daily-next");
  const dailyCheckPending = qs("#daily-check-pending");
  const dailyApproveAll = qs("#daily-approve-all");
  const dailyBulkReject = qs("#daily-bulk-reject");
  const dialogSave = qs("#dialog-save");
  const dialogRestore = qs("#dialog-restore");
  const dailySubmit = qs("#daily-submit");
  const dailyExport = qs("#daily-export");
  const dailyExportAll = qs("#daily-export-all");
  const refreshHealth = qs("#refresh-health");
  
  if (dailyBatch) dailyBatch.addEventListener("change", async (e) => { state.batchId = e.target.value; state.page = 1; if (state.batchId) await loadBatch(); });
  qsa(".source-tab").forEach((button) => button.addEventListener("click", async () => { qsa(".source-tab").forEach((x) => x.classList.toggle("is-active", x === button)); state.sourceType = button.dataset.sourceType; state.page = 1; await loadItems(); }));
  if (dailyPrev) dailyPrev.addEventListener("click", () => { if (state.page > 1) { state.page--; loadItems().catch(showError); } });
  if (dailyNext) dailyNext.addEventListener("click", () => { if (state.page < state.pages) { state.page++; loadItems().catch(showError); } });
  if (dailyCheckPending) dailyCheckPending.addEventListener("click", async () => {
    try {
      setStatus("#daily-status", "🔍 Checking all items...", "info");
      let totalPending = 0;
      let page = 1;
      let hasMore = true;
      
      while (hasMore && page <= 50) {
        const items = await request(`/api/daily-intelligence/batches/${state.batchId}/items?page=${page}&page_size=100&review_status=pending`);
        totalPending += items.items.length;
        hasMore = items.items.length === 100;
        page++;
      }
      
      if (totalPending === 0) {
        setStatus("#daily-status", "✓ No pending items found! Safe to submit.", "success");
      } else {
        setStatus("#daily-status", `⚠️ Found ${totalPending} pending items across all pages. Click "Approve All Pending" to fix.`, "error");
      }
    } catch (e) {
      showError(e);
    }
  });
  if (dailyApproveAll) dailyApproveAll.addEventListener("click", async () => { try { await autoApprovePending(); await loadItems(); } catch(e) { showError(e); } });
  if (dailyBulkReject) dailyBulkReject.addEventListener("click", () => bulkReject().catch(showError));
  if (dialogSave) dialogSave.addEventListener("click", async () => { const s = state.editing.summary; await request(`/api/daily-intelligence/summaries/${s.id}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({edited_summary_text: qs("#dialog-summary").value, reviewer_notes: qs("#dialog-notes").value})}); qs("#summary-dialog").close(); await loadItems(); });
  if (dialogRestore) dialogRestore.addEventListener("click", async () => { await request(`/api/daily-intelligence/summaries/${state.editing.summary.id}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({restore_original: true})}); qs("#summary-dialog").close(); await loadItems(); });
  if (dailySubmit) dailySubmit.addEventListener("click", async () => { 
    try {
      // Auto-approve any remaining pending items before submission
      setStatus("#daily-status", "Preparing batch for submission...", "info");
      const approved = await autoApprovePending();
      
      // Reload items to see current state
      await loadItems();
      
      // Check if there are still pending items (shouldn't happen but defensive check)
      const hasPending = [...state.items.values()].some(item => item.review_status === "pending");
      
      if (hasPending) {
        const pendingCount = [...state.items.values()].filter(item => item.review_status === "pending").length;
        setStatus("#daily-status", `⚠️ ${pendingCount} items still pending. Some items may not have summaries. Try "Approve All Pending" button or check console.`, "error");
        console.error("Pending items found:", [...state.items.values()].filter(item => item.review_status === "pending"));
        return;
      }
      
      const confirmMsg = approved > 0 
        ? `✓ Auto-approved ${approved} items.\n\nLock and submit this batch for publication?\n\nRejected items will be excluded.\nAll approved items will be published.\n\nThis cannot be undone.`
        : `Lock and submit this batch for publication?\n\nRejected items will be excluded.\nAll approved items will be published.\n\nThis cannot be undone.`;
      
      if (!confirm(confirmMsg)) return;
      
      setStatus("#daily-status", "Submitting batch...", "info");
      await request(`/api/daily-intelligence/batches/${state.batchId}/submit-review`, {method: "POST"}); 
      setStatus("#daily-status", "✓ Batch submitted! All non-rejected items approved for publication.", "success");
      await loadBatch(); 
    } catch(e) {
      // Enhanced error handling for 409 conflicts
      if (e.status === 409 && e.body?.detail) {
        const match = e.body.detail.match(/(\d+) items still require/);
        if (match) {
          const count = match[1];
          setStatus("#daily-status", `⚠️ ${count} items are still pending! Click "Approve All Pending" button, wait for 100%, then try Submit again.`, "error");
          console.error("409 Conflict details:", e.body);
          return;
        }
      }
      showError(e); 
    } 
  });
  if (dailyExport) dailyExport.addEventListener("click", () => {
    if (!state.batchId) return setStatus("#daily-status", "Select or run a batch first.", "error");
    downloadPdf(`/api/daily-intelligence/batches/${state.batchId}/export.pdf`, dailyExport, `BridgeAI_Daily_Intelligence_${state.batchId}.pdf`);
  });
  if (dailyExportAll) dailyExportAll.addEventListener("click", () => downloadPdf("/api/daily-intelligence/export-all.pdf", dailyExportAll, "BridgeAI_Comprehensive_Daily_Intelligence.pdf"));
  if (refreshHealth) refreshHealth.addEventListener("click", async () => renderHealth(await request("/api/daily-intelligence/source-health")));
  
  loadBatches().catch(showError);
});

// Signal Filter is intentionally isolated for post-processing Daily Intelligence output
document.addEventListener("DOMContentLoaded", () => {
  const filterForm = qs("#filter-form");
  if (!filterForm) return;
  
  let currentFilterResult = null;
  let currentEditorialBrief = null;

  async function loadFilterBatches() {
    try {
      const batches = await request("/api/daily-intelligence/batches?limit=50");
      const select = qs("#filter-batch");
      
      // Filter for approved batches (submitted and locked)
      const approvedBatches = batches.filter(b => b.review_locked && b.status === "approved");
      
      // Also show batches that are awaiting_review for debugging
      const awaitingBatches = batches.filter(b => b.status === "awaiting_review" && !b.review_locked);
      
      if (approvedBatches.length > 0) {
        select.innerHTML = approvedBatches.map((b) => 
          `<option value="${escapeHtml(b.id)}">${escapeHtml(new Date(b.created_at).toLocaleString())} - ${b.approved_items} approved items</option>`
        ).join("");
      } else if (awaitingBatches.length > 0) {
        select.innerHTML = `<option value="">No approved batches yet - ${awaitingBatches.length} awaiting review (submit them first)</option>`;
        setStatus("#filter-status", `${awaitingBatches.length} batch(es) found but not submitted. Go to Daily Intelligence → Submit Review first.`, "error");
      } else {
        select.innerHTML = `<option value="">No batches yet - run Daily Intelligence first</option>`;
      }
    } catch (e) {
      setStatus("#filter-status", normalizeError(e), "error");
    }
  }

  function renderFilterResults(data) {
    const summary = data.summary || {};
    const items = data.filtered_items || [];
    const sections = data.sections || [];
    
    setCard("#filter-output", "filter-summary", {
      input_items: summary.input_items || 0,
      output_items: summary.output_items || 0,
      removed_duplicates: summary.removed_duplicates || 0,
      removed_low_quality: summary.removed_low_quality || 0,
      clustering_applied: summary.clustering_applied || false,
      qa_checks_applied: summary.qa_checks_applied || false,
    });
    
    const renderSignal = (item) => `
          <div class="filter-signal-card">
            <h4>${escapeHtml(item.title)}</h4>
            <div class="signal-meta">
              <span>Novelty: ${item.novelty_score?.toFixed(1) || 'N/A'}</span>
              <span>Relevance: ${item.relevance_score || 'N/A'}</span>
              <span>${escapeHtml(item.source_type)}</span>
            </div>
            <p>${escapeHtml(item.why_it_matters || item.summary || '')}</p>
            ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">View Source</a>` : ''}
          </div>
        `;
    const itemsHtml = items.length 
      ? (sections.length ? sections.map(group => `
          <section class="filter-section" data-section="${escapeHtml(group.section)}">
            <h3>${escapeHtml(group.section)} <span class="status-pill">${group.count}</span></h3>
            ${group.items.map(renderSignal).join("")}
          </section>
        `).join("") : items.map(renderSignal).join(""))
      : `<div class="empty">No signals passed the filter.</div>`;
    
    qs("#filter-output [data-card='filtered-items'] .card-body").innerHTML = itemsHtml;
    
    const downloadBtn = qs("#download-filtered-pdf");
    const editorialBtn = qs("#generate-editorial-brief");
    const editorialDownloadBtn = qs("#download-editorial-brief");
    const actionsBody = qs("#filter-output [data-card='filter-actions'] .card-body");
    downloadBtn.disabled = items.length === 0;
    editorialBtn.disabled = items.length === 0;
    currentEditorialBrief = null;
    editorialDownloadBtn.disabled = true;
    actionsBody.querySelector("p").textContent = items.length > 0 
      ? `${items.length} high-quality signals ready for export.`
      : "No signals to export. Try adjusting filter thresholds.";
  }

  function renderEditorialBrief(brief) {
    const sections = brief.sections || [];
    const html = `
      <div class="editorial-issue-head">
        <p class="eyebrow">Subject line</p>
        <h3>${escapeHtml(brief.subject_line || "")}</h3>
        <p><strong>This Week in Brief:</strong> ${escapeHtml(brief.this_week_in_brief || "")}</p>
        <p class="empty small">${escapeHtml(brief.generation_mode || "")} · ${brief.item_count || 0} editorial items</p>
      </div>
      ${sections.map(group => `
        <section class="editorial-section">
          <h3>${escapeHtml(group.section)} <span class="status-pill">${group.count}</span></h3>
          ${(group.items || []).map(item => `
            <article class="editorial-item">
              <h4>${escapeHtml(item.headline)}</h4>
              <p><strong>What happened:</strong> ${escapeHtml(item.what_happened)}</p>
              <p><strong>Why it matters:</strong> ${escapeHtml(item.why_it_matters)}</p>
              <p><strong>The move:</strong> ${escapeHtml(item.the_move)}</p>
              <p><strong>Function:</strong> ${escapeHtml(item.function)}</p>
              <p><strong>Source:</strong> ${item.source?.url
                ? `<a href="${escapeHtml(item.source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.source.publication)}${item.source.published_at ? `, ${escapeHtml(new Date(item.source.published_at).toLocaleDateString())}` : ""}</a>`
                : `${escapeHtml(item.source?.publication || "Unavailable")} — link unavailable in source data`}</p>
            </article>
          `).join("")}
        </section>
      `).join("")}`;
    qs("#filter-output [data-card='editorial-brief'] .card-body").innerHTML = html;
  }

  filterForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const batchId = qs("#filter-batch").value;
    
    if (!batchId) {
      setStatus("#filter-status", "Please select a batch to filter.", "error");
      return;
    }

    const payload = {
      batch_id: batchId,
      novelty_threshold: Number(formData.get("novelty_threshold") || 0),
      relevance_threshold: Number(formData.get("relevance_threshold") || 0),
      max_items: Number(formData.get("max_items") || 20),
      enable_clustering: Boolean(formData.get("enable_clustering")),
      enable_qa: Boolean(formData.get("enable_qa")),
    };

    setLoading(form, true, "Applying signal filter...", "#filter-status");
    const progress = startProgress("#filter-status", [
      "Loading approved items...",
      "Calculating novelty scores...",
      "Applying relevance filters...",
      "Clustering similar signals...",
      "Running QA checks...",
      "Finalizing filtered set...",
    ]);

    try {
      const data = await request("/api/signal-filter/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      currentFilterResult = data;
      renderFilterResults(data);
      setDebug("Signal Filter response", data);
      setStatus("#filter-status", `✓ Filter complete. ${data.summary?.output_items || 0} of ${data.summary?.input_items || 0} items passed.`, "success");
    } catch (error) {
      const message = normalizeError(error);
      setDebug("Signal Filter error", { status: error.status, message: error.message, body: error.body });
      setStatus("#filter-status", message, "error");
    } finally {
      window.clearInterval(progress);
      setLoading(form, false, "", "#filter-status");
    }
  });

  qs("#download-filtered-pdf")?.addEventListener("click", async () => {
    if (!currentFilterResult || !currentFilterResult.run_id) {
      setStatus("#filter-status", "No filter result to download. Apply filter first.", "error");
      return;
    }
    
    const button = qs("#download-filtered-pdf");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Generating PDF...";
    
    try {
      const response = await fetch(`/api/signal-filter/runs/${currentFilterResult.run_id}/export.pdf`, {
        headers: { Accept: "application/pdf" }
      });
      
      if (!response.ok) throw new Error(await response.text() || `PDF export failed (${response.status})`);
      
      const blob = await response.blob();
      if (blob.type !== "application/pdf" || blob.size < 1000) {
        throw new Error("The server returned an empty or invalid PDF.");
      }
      
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = match?.[1] || `BridgeAI_Filtered_Signals_${currentFilterResult.run_id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      setStatus("#filter-status", `Downloaded ${blob.size.toLocaleString()} bytes of filtered signals.`, "success");
    } catch (error) {
      setStatus("#filter-status", normalizeError(error), "error");
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });

  qs("#generate-editorial-brief")?.addEventListener("click", async () => {
    if (!currentFilterResult?.run_id) {
      setStatus("#filter-status", "Apply the signal filter before generating an editorial brief.", "error");
      return;
    }
    const button = qs("#generate-editorial-brief");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Creating Editorial Brief...";
    setStatus("#filter-status", "Applying the Bridge AI editorial lens to filtered signals...", "info");
    try {
      const brief = await request(`/api/signal-filter/runs/${currentFilterResult.run_id}/editorial-brief`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({use_ai: true}),
      });
      currentEditorialBrief = brief;
      renderEditorialBrief(brief);
      qs("#download-editorial-brief").disabled = false;
      setDebug("Editorial Ready Brief", brief);
      setStatus("#filter-status", `Editorial brief ready with ${brief.item_count || 0} source-backed items.`, "success");
    } catch (error) {
      setStatus("#filter-status", normalizeError(error), "error");
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });

  qs("#download-editorial-brief")?.addEventListener("click", async () => {
    if (!currentFilterResult?.run_id || !currentEditorialBrief) {
      setStatus("#filter-status", "Generate the editorial brief before downloading it.", "error");
      return;
    }
    const button = qs("#download-editorial-brief");
    await downloadPdf(
      `/api/signal-filter/runs/${currentFilterResult.run_id}/editorial-brief.pdf`,
      button,
      `BridgeAI_Editorial_Brief_${currentFilterResult.run_id.slice(0, 8)}.pdf`,
      "#filter-status",
    );
  });

  loadFilterBatches();
});
