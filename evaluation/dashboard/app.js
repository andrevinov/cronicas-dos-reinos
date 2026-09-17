(() => {
  "use strict";

  const SESSION_INDEX = "../sessions/index.json";
  const PT = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  const INTEGER = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
  const AXIS_LABELS = {
    calibracao: "Calibração",
    eficacia_integridade: "Eficácia operacional",
    confiabilidade: "Confiabilidade",
    economia: "Economia",
    fluidez: "Fluidez",
    jogador: "Jogador",
  };
  const MODULE_SCORE_FIELDS = {
    calibracao: "nota_calibracao_0a100",
    eficacia_integridade: "nota_eficacia_integridade_0a100",
    confiabilidade: "nota_confiabilidade_proxy_0a100",
    economia: "nota_economia_0a100",
    fluidez: "nota_fluidez_exposta_0a100",
    jogador: "nota_jogador_0a100",
  };
  const state = {
    index: null,
    sessionEntry: null,
    scorecard: null,
    modules: [],
    feedbackRows: [],
    feedback: {},
    interactions: [],
    manifestations: [],
    localManifestations: [],
    releases: [],
  };

  const $ = (selector) => document.querySelector(selector);

  function number(value) {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function clamp(value, min = 0, max = 100) {
    return Math.max(min, Math.min(max, value));
  }

  function scoreBand(score) {
    if (score === null) return "N/D";
    if (score >= 90) return "excelente";
    if (score >= 80) return "saudável";
    if (score >= 65) return "atenção";
    if (score >= 50) return "ruim";
    return "crítico";
  }

  function scoreColor(score) {
    if (score === null) return "#899892";
    if (score >= 80) return "#6bc49f";
    if (score >= 65) return "#e0ae52";
    if (score >= 50) return "#ec9962";
    return "#e37c72";
  }

  function formatScore(value) {
    const parsed = number(value);
    return parsed === null ? "N/D" : PT.format(parsed);
  }

  function formatPercent(value, alreadyPercent = false) {
    const parsed = number(value);
    if (parsed === null) return "N/D";
    return `${PT.format(alreadyPercent ? parsed : parsed * 100)}%`;
  }

  function formatSeconds(value) {
    const parsed = number(value);
    return parsed === null ? "N/D" : `${PT.format(parsed)} s`;
  }

  function formatTokens(value) {
    const parsed = number(value);
    if (parsed === null) return "N/D";
    if (parsed >= 1_000_000) return `${PT.format(parsed / 1_000_000)} mi`;
    if (parsed >= 1_000) return `${PT.format(parsed / 1_000)} mil`;
    return INTEGER.format(parsed);
  }

  function friendlyModuleName(id) {
    return String(id)
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function create(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  async function sha256(textValue) {
    const bytes = new TextEncoder().encode(textValue);
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
  }

  async function fetchJSON(path) {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  async function fetchText(path) {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.text();
  }

  function parseCSV(text) {
    const rows = [];
    let row = [];
    let field = "";
    let quoted = false;
    const source = text.replace(/^\uFEFF/, "");
    for (let index = 0; index < source.length; index += 1) {
      const char = source[index];
      if (quoted) {
        if (char === '"' && source[index + 1] === '"') {
          field += '"';
          index += 1;
        } else if (char === '"') {
          quoted = false;
        } else {
          field += char;
        }
      } else if (char === '"') {
        quoted = true;
      } else if (char === ",") {
        row.push(field);
        field = "";
      } else if (char === "\n") {
        row.push(field.replace(/\r$/, ""));
        rows.push(row);
        row = [];
        field = "";
      } else {
        field += char;
      }
    }
    if (field || row.length) {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
    }
    const headers = rows.shift() || [];
    return rows
      .filter((values) => values.some((value) => value !== ""))
      .map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] || ""])));
  }

  function csvEscape(value) {
    const text = String(value ?? "");
    return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  }

  function toCSV(rows) {
    const columns = [
      "tipo",
      "item",
      "rotulo",
      "observado",
      "nota_1a5",
      "ativacao_menos2a2",
      "impacto_menos2a2",
      "comentario",
    ];
    return [
      columns.join(","),
      ...rows.map((row) => columns.map((column) => csvEscape(row[column])).join(",")),
    ].join("\r\n") + "\r\n";
  }

  function feedbackKey(row) {
    return `${row.tipo}:${row.item}`;
  }

  function storageKey() {
    return `cronicas-avaliacao-feedback:${state.sessionEntry.sessao_id}`;
  }

  function manifestationStorageKey() {
    return `cronicas-avaliacao-manifestacoes:${state.sessionEntry.sessao_id}`;
  }

  function isV2() {
    return state.sessionEntry?.serie_avaliacao === "modules-v2";
  }

  function hasIndependentPriorityQueues() {
    return state.scorecard?.filas_prioridade?.schema === 1;
  }

  function comparisonKey(entry) {
    if (Array.isArray(entry.chave_comparabilidade) && entry.chave_comparabilidade.length) {
      return JSON.stringify(entry.chave_comparabilidade);
    }
    return JSON.stringify([entry.serie_avaliacao || "legacy-v1", "versoes_ausentes"]);
  }

  function comparableSessions() {
    const current = comparisonKey(state.sessionEntry);
    return (state.index.sessoes || []).filter((entry) => comparisonKey(entry) === current);
  }

  function loadStoredFeedback() {
    let stored = {};
    try {
      stored = JSON.parse(localStorage.getItem(storageKey()) || "{}") || {};
    } catch (_error) {
      stored = {};
    }
    state.feedback = {};
    for (const row of state.feedbackRows) {
      const key = feedbackKey(row);
      state.feedback[key] = { ...row, ...(stored[key] || {}) };
    }
  }

  function saveFeedback() {
    localStorage.setItem(storageKey(), JSON.stringify(state.feedback));
    $("#saveStatus").textContent = "Alterações salvas neste navegador.";
  }

  function playerScores() {
    const global = [];
    const modules = {};
    for (const row of Object.values(state.feedback)) {
      const score = number(row.nota_1a5);
      if (score === null || score < 1 || score > 5) continue;
      const normalized = (score - 1) * 25;
      if (row.tipo === "global") global.push(normalized);
      if (row.tipo === "modulo") modules[row.item] = normalized;
    }
    return {
      global: global.length ? global.reduce((sum, value) => sum + value, 0) / global.length : null,
      modules,
      answered: global.length,
    };
  }

  function weightedScore(scores, weights) {
    let total = 0;
    let weightTotal = 0;
    for (const [key, score] of Object.entries(scores)) {
      const parsed = number(score);
      const weight = number(weights[key]);
      if (parsed === null || weight === null) continue;
      total += parsed * weight;
      weightTotal += weight;
    }
    return weightTotal ? total / weightTotal : null;
  }

  function previewSessionScore() {
    if (isV2()) return { score: number(state.scorecard.nota_geral_0a100), player: null };
    const player = playerScores().global;
    const scores = {};
    const weights = {};
    for (const [key, item] of Object.entries(state.scorecard.eixos || {})) {
      scores[key] = key === "jogador" && player !== null ? player : item.nota_0a100;
      weights[key] = item.peso;
    }
    return { score: weightedScore(scores, weights), player };
  }

  function previewModuleScore(module) {
    if (isV2()) return number(module.nota_desempenho_provisoria_0a100);
    const localPlayer = playerScores().modules[module.modulo];
    if (localPlayer === undefined) return number(module.nota_desempenho_provisoria_0a100);
    const scores = {};
    const weights = {};
    for (const [key, item] of Object.entries(state.scorecard.eixos || {})) {
      scores[key] = key === "jogador" ? localPlayer : module[MODULE_SCORE_FIELDS[key]];
      weights[key] = item.peso;
    }
    return weightedScore(scores, weights);
  }

  function renderScore() {
    const preview = previewSessionScore();
    const original = number(state.scorecard.nota_geral_0a100);
    const score = preview.score;
    const hasPlayer = !isV2() && preview.player !== null;
    const aggregation = state.scorecard.agregacao_modular || {};
    const aggregationBlocked = isV2() && aggregation.conclusao_permitida === false;
    const measurementConclusion = state.scorecard.conclusao_medicao || {};
    const conclusionBlocked = isV2() && measurementConclusion.permitida === false;
    $("#overallScore").textContent = formatScore(score);
    $("#overallBand").textContent = scoreBand(score);
    $("#scoreMode").textContent = conclusionBlocked
      ? "Desempenho observado · conclusão bloqueada"
      : aggregationBlocked
      ? "Desempenho operacional parcial · instrumentação bloqueada"
      : hasPlayer
        ? "Prévia com sua percepção"
        : "Desempenho operacional provisório";
    const ring = $("#scoreRing");
    ring.style.setProperty("--score", clamp(score || 0));
    ring.style.setProperty("--ring-color", scoreColor(score));
    $("#previewScore").textContent = hasPlayer ? formatScore(score) : "N/D";
    const player = playerScores();
    if (isV2()) {
      const total = state.manifestations.length + state.localManifestations.length;
      $("#feedbackStatus").textContent = `${total} manifestação(ões)`;
      $("#feedbackStatus").className = "badge badge-muted";
    } else {
      $("#playerAverage").textContent = hasPlayer
        ? `Sua percepção: ${formatScore(player.global)} · ${player.answered} quesito(s)`
        : "Preencha ao menos um quesito global";
      $("#feedbackStatus").textContent = hasPlayer ? "Feedback local ativo" : "Feedback pendente";
      $("#feedbackStatus").className = `badge ${hasPlayer ? "" : "badge-muted"}`.trim();
    }

    const entries = comparableSessions();
    const currentIndex = entries.findIndex((item) => item.sessao_id === state.sessionEntry.sessao_id);
    const previous = currentIndex > 0 ? number(entries[currentIndex - 1].nota_geral_0a100) : null;
    if (conclusionBlocked) {
      const reasons = (measurementConclusion.bloqueios || []).map((item) => item.codigo).join(", ");
      $("#scoreDelta").textContent = `Conclusão bloqueada${reasons ? `: ${reasons}` : ""}`;
    } else if (aggregationBlocked) {
      $("#scoreDelta").textContent = "Conclusão bloqueada; componentes inválidos foram excluídos";
    } else if (previous === null) {
      $("#scoreDelta").textContent = hasPlayer && original !== null
        ? `${formatScore(score - original)} ponto(s) pela percepção local`
        : "Primeira medição";
    } else {
      const delta = score - previous;
      $("#scoreDelta").textContent = `${delta >= 0 ? "+" : ""}${PT.format(delta)} vs. sessão anterior`;
    }
  }

  function renderHeader() {
    const metrics = state.scorecard.indicadores_globais || {};
    const aggregation = state.scorecard.agregacao_modular || {};
    const conclusion = state.scorecard.conclusao_medicao || {};
    const aggregationSummary = aggregation.modulos_catalogados === undefined
      ? `${state.modules.length} módulos catalogados`
      : `${aggregation.modulos_incluidos} de ${aggregation.modulos_catalogados} módulos incluídos`;
    $("#sessionTitle").textContent = `Sessão ${state.sessionEntry.sessao_id}`;
    $("#confidenceLabel").textContent = state.scorecard.confianca?.sessao || "N/D";
    $("#sessionSummary").textContent = `${INTEGER.format(metrics.turnos_narrativos || 0)} turnos narrativos, ${aggregationSummary} e ${formatTokens(metrics.input_tokens)} tokens de entrada observados.`;
    const conclusionLabel = conclusion.permitida === false ? " · conclusão bloqueada" : "";
    $("#evaluationStatus").textContent = `Avaliação ${state.scorecard.status_avaliacao || "N/D"}${conclusionLabel}`;
    $("#seriesStatus").textContent = isV2() ? "modules-v2" : "legado v1";
    $("#moduleCount").textContent = `${state.modules.length} módulos catalogados`;
    $("#reportLink").href = `../sessions/${state.sessionEntry.caminho}/relatorio.md`;
    renderScore();
  }

  function renderAxes() {
    const container = $("#axesGrid");
    container.replaceChildren();
    const localPlayer = playerScores().global;
    for (const [key, item] of Object.entries(state.scorecard.eixos || {})) {
      const score = key === "jogador" && localPlayer !== null ? localPlayer : number(item.nota_0a100);
      const card = create("article", "axis-card");
      const top = create("div", "axis-top");
      top.append(create("span", "", AXIS_LABELS[key] || key), create("strong", "", formatScore(score)));
      const bar = create("div", "bar");
      const fill = create("span");
      fill.style.setProperty("--width", `${clamp(score || 0)}%`);
      fill.style.setProperty("--bar-color", scoreColor(score));
      bar.append(fill);
      const denominator = state.scorecard.agregacao_modular?.denominadores?.[key];
      const validComponents = denominator
        ? (denominator.componentes_validos ?? denominator.componentes_modulares_validos ?? 0)
          + (denominator.componentes_globais_validos?.length || 0)
        : null;
      const denominatorLabel = validComponents === null
        ? ""
        : ` · ${validComponents} componente(s) válido(s)`;
      card.append(top, bar, create("small", "", `Peso ${item.peso}% · ${scoreBand(score)}${denominatorLabel}`));
      container.append(card);
    }
  }

  function metricCard(label, value, target, good) {
    const card = create("article", `metric-card ${good === true ? "good" : good === false ? "bad" : ""}`);
    card.append(create("span", "", label), create("strong", "", value), create("small", "", target));
    return card;
  }

  function renderMetrics() {
    const metrics = state.scorecard.indicadores_globais || {};
    const rows = [
      ["Redução de input", formatPercent(metrics.reducao_input_bruto_baseline), "meta ≥ 70%", number(metrics.reducao_input_bruto_baseline) >= 0.7],
      ["Inferências por turno", formatScore(metrics.inferencias_por_turno), "meta ≤ 5", number(metrics.inferencias_por_turno) <= 5],
      ["Tools por turno", formatScore(metrics.tools_por_turno), "meta ≤ 5", number(metrics.tools_por_turno) <= 5],
      ["L0–L2 limpo", formatPercent(metrics.fracao_l0_l2_limpo), "meta ≥ 80%", number(metrics.fracao_l0_l2_limpo) >= 0.8],
      ["Latência mediana", formatSeconds(metrics.latencia_mediana_segundos), "referência ≤ 60 s", number(metrics.latencia_mediana_segundos) <= 60],
      ["Latência p90", formatSeconds(metrics.latencia_p90_segundos), "referência ≤ 120 s", number(metrics.latencia_p90_segundos) <= 120],
      ["Turnos com RAW", formatPercent(metrics.fracao_turnos_com_raw), `${metrics.raw_read_calls || 0} leituras cruas`, null],
      ["Schema discovery", INTEGER.format(metrics.schema_discovery_calls || 0), "meta = 0", number(metrics.schema_discovery_calls) === 0],
      ["Par crônica exato", formatPercent(metrics.fracao_par_cronica_exato), "preferência = 100%", number(metrics.fracao_par_cronica_exato) === 1],
      ["Input não-cache", formatTokens(metrics.uncached_input_tokens_aprox), "aproximação operacional", null],
      ["Compactações", INTEGER.format(metrics.compactacoes || 0), "eventos no rollout", null],
      ["Turnos acima de 300 s", INTEGER.format(metrics.turnos_acima_300_segundos || 0), "outliers severos", number(metrics.turnos_acima_300_segundos) === 0],
    ];
    const container = $("#metricsGrid");
    container.replaceChildren(...rows.map((row) => metricCard(...row)));
  }

  function renderTrend() {
    const metric = $("#trendMetric").value;
    const values = comparableSessions()
      .map((entry) => ({
        id: entry.sessao_id,
        value: metric === "geral"
          ? number(entry.nota_geral_0a100)
          : number(entry.eixos?.[metric]?.nota_0a100),
      }))
      .filter((item) => item.value !== null);
    const container = $("#trendChart");
    container.replaceChildren();
    if (!values.length) {
      container.append(create("p", "trend-empty", "Ainda não há medições para este eixo."));
      return;
    }
    const width = 680;
    const height = 190;
    const padding = { left: 42, right: 24, top: 18, bottom: 34 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const x = (index) => values.length === 1
      ? padding.left + innerWidth / 2
      : padding.left + (index / (values.length - 1)) * innerWidth;
    const y = (value) => padding.top + ((100 - value) / 100) * innerHeight;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `Tendência de ${metric === "geral" ? "nota geral" : AXIS_LABELS[metric]}`);
    for (const tick of [0, 25, 50, 75, 100]) {
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", padding.left);
      line.setAttribute("x2", width - padding.right);
      line.setAttribute("y1", y(tick));
      line.setAttribute("y2", y(tick));
      line.setAttribute("stroke", tick === 0 ? "var(--line-strong)" : "var(--line)");
      line.setAttribute("stroke-dasharray", tick === 0 ? "0" : "4 5");
      svg.append(line);
      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", padding.left - 10);
      label.setAttribute("y", y(tick) + 4);
      label.setAttribute("text-anchor", "end");
      label.setAttribute("font-size", "10");
      label.setAttribute("fill", "var(--muted)");
      label.textContent = String(tick);
      svg.append(label);
    }
    if (values.length > 1) {
      const path = document.createElementNS(ns, "polyline");
      path.setAttribute("points", values.map((item, index) => `${x(index)},${y(item.value)}`).join(" "));
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "var(--forest-2)");
      path.setAttribute("stroke-width", "3");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      svg.append(path);
    }
    values.forEach((item, index) => {
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", x(index));
      circle.setAttribute("cy", y(item.value));
      circle.setAttribute("r", item.id === state.sessionEntry.sessao_id ? "7" : "5");
      circle.setAttribute("fill", scoreColor(item.value));
      circle.setAttribute("stroke", "var(--surface)");
      circle.setAttribute("stroke-width", "3");
      svg.append(circle);
      const label = document.createElementNS(ns, "text");
      label.setAttribute("x", x(index));
      label.setAttribute("y", height - 10);
      label.setAttribute("text-anchor", "middle");
      label.setAttribute("font-size", "10");
      label.setAttribute("fill", "var(--muted)");
      label.textContent = `S${item.id}`;
      svg.append(label);
      const valueLabel = document.createElementNS(ns, "text");
      valueLabel.setAttribute("x", x(index));
      valueLabel.setAttribute("y", y(item.value) - 12);
      valueLabel.setAttribute("text-anchor", "middle");
      valueLabel.setAttribute("font-size", "12");
      valueLabel.setAttribute("font-weight", "700");
      valueLabel.setAttribute("fill", "var(--ink)");
      valueLabel.textContent = formatScore(item.value);
      svg.append(valueLabel);
    });
    container.append(svg);
    container.append(create("p", "trend-empty", values.length === 1
      ? "Primeiro ponto da série. A próxima sessão formará a primeira comparação."
      : `${values.length} sessões comparáveis nesta série.`));
  }

  function renderInsights() {
    const scored = state.modules.filter((module) => number(previewModuleScore(module)) !== null);
    const best = [...scored].sort((a, b) => previewModuleScore(b) - previewModuleScore(a))[0];
    const worst = [...scored].sort((a, b) => previewModuleScore(a) - previewModuleScore(b))[0];
    const firstRanked = (field) => [...state.modules]
      .filter((module) => number(module[field]) !== null)
      .sort((a, b) => number(a[field]) - number(b[field]))[0];
    const repair = firstRanked("fila_reparo_medidor_rank");
    const experience = firstRanked("fila_experiencia_rank");
    const costly = hasIndependentPriorityQueues()
      ? firstRanked("fila_investigacao_custo_rank")
      : [...state.modules].sort((a, b) => number(b.tokens_totais_atribuidos_fracionados) - number(a.tokens_totais_atribuidos_fracionados))[0];
    const entries = hasIndependentPriorityQueues() ? [
      ["↑", "Melhor nota", best, best ? formatScore(previewModuleScore(best)) : "N/D"],
      ["↓", "Pior nota", worst, worst ? formatScore(previewModuleScore(worst)) : "N/D"],
      ["!", "Reparo do medidor", repair, repair ? `#${repair.fila_reparo_medidor_rank}` : "fila vazia"],
      ["◇", "Problema da experiência", experience, experience ? `#${experience.fila_experiencia_rank}` : "sem adjudicação"],
      ["¤", "Maior atribuição contábil", costly, costly ? formatTokens(costly.tokens_totais_atribuidos_fracionados) : "N/D"],
    ] : [
      ["↑", "Melhor nota", best, best ? formatScore(previewModuleScore(best)) : "N/D"],
      ["↓", "Pior nota", worst, worst ? formatScore(previewModuleScore(worst)) : "N/D"],
      ["!", "Maior prioridade", firstRanked("prioridade_rank"), firstRanked("prioridade_rank") ? `#${firstRanked("prioridade_rank").prioridade_rank}` : "N/D"],
      ["¤", "Maior custo", costly, costly ? formatTokens(costly.tokens_totais_atribuidos_fracionados) : "N/D"],
    ];
    const container = $("#insights");
    container.replaceChildren();
    for (const [icon, label, module, value] of entries) {
      const card = create("div", "insight");
      const iconElement = create("span", "insight-icon", icon);
      const copy = create("div");
      const moduleName = module ? friendlyModuleName(module.modulo) : "Sem dados";
      const nameElement = create("span", "", moduleName);
      nameElement.title = moduleName;
      copy.append(create("small", "", label), nameElement);
      card.append(iconElement, copy, create("strong", "", value));
      container.append(card);
    }
  }

  function activationClass(value) {
    if (value === "ativou a contento") return "ok";
    if (["sobreativou", "subativou", "falha de instrumentação"].includes(value)) return "over";
    return "";
  }

  function renderModules() {
    const search = $("#moduleSearch").value.trim().toLocaleLowerCase("pt-BR");
    const filter = $("#activationFilter").value;
    const sort = $("#moduleSort").value;
    let modules = state.modules.filter((module) => {
      const activationMatch = filter === "todos" || module.avaliacao_ativacao === filter;
      const haystack = `${module.modulo} ${module.responsabilidade}`.toLocaleLowerCase("pt-BR");
      return activationMatch && (!search || haystack.includes(search));
    });
    const sorters = {
      experiencia: (a, b) => (number(a.fila_experiencia_rank) ?? 999) - (number(b.fila_experiencia_rank) ?? 999) || String(a.modulo).localeCompare(String(b.modulo)),
      reparo: (a, b) => (number(a.fila_reparo_medidor_rank) ?? 999) - (number(b.fila_reparo_medidor_rank) ?? 999) || String(a.modulo).localeCompare(String(b.modulo)),
      prioridade: (a, b) => (number(a.prioridade_rank) ?? 999) - (number(b.prioridade_rank) ?? 999),
      pior: (a, b) => (number(previewModuleScore(a)) ?? Infinity) - (number(previewModuleScore(b)) ?? Infinity),
      melhor: (a, b) => (number(previewModuleScore(b)) ?? -Infinity) - (number(previewModuleScore(a)) ?? -Infinity),
      custo: (a, b) => number(b.tokens_totais_atribuidos_fracionados) - number(a.tokens_totais_atribuidos_fracionados),
      frequencia: (a, b) => number(b.turnos_detectados) - number(a.turnos_detectados),
    };
    modules = [...modules].sort(sorters[sort]);
    const container = $("#moduleGrid");
    container.replaceChildren();
    $("#moduleEmpty").hidden = modules.length > 0;
    for (const module of modules) {
      const moduleScore = number(previewModuleScore(module));
      const instrumentationFailure = module.avaliacao_ativacao === "falha de instrumentação";
      const notApplicable = module.aplicabilidade_avaliacao === "nao_aplicavel";
      const indeterminate = module.aplicabilidade_avaliacao === "indeterminado";
      const scoreText = instrumentationFailure ? "ERRO" : (notApplicable || indeterminate) ? "—" : formatScore(moduleScore);
      const scoreState = instrumentationFailure ? "telemetria incompleta" : notApplicable ? "não aplicável" : indeterminate ? "indeterminado" : scoreBand(moduleScore);
      const card = create("article", "module-card");
      card.style.setProperty("--module-color", instrumentationFailure ? "#e37c72" : scoreColor(moduleScore));
      const header = create("div", "module-card-header");
      const name = create("div");
      const versionRow = create("div", "module-version-row");
      versionRow.append(
        create("span", "module-version", `Módulo v${module.versao_implementacao || "N/D"}`),
        create("span", "evaluation-version", `Avaliação v${module.versao_avaliacao || "N/D"}`),
      );
      name.append(
        create("h3", "", friendlyModuleName(module.modulo)),
        create("span", "module-id", module.modulo),
        versionRow,
      );
      const scoreBox = create("div", "module-score");
      scoreBox.append(create("strong", "", scoreText), create("small", "", scoreState));
      header.append(name, scoreBox);
      const description = create("p", "module-description", module.responsabilidade);
      const meta = create("div", "module-meta");
      meta.append(
        create("span", `pill ${activationClass(module.avaliacao_ativacao)}`, module.avaliacao_ativacao),
        create("span", "pill", `Confiança ${module.confianca_amostra_sessao}`),
      );
      if (hasIndependentPriorityQueues()) {
        if (number(module.fila_reparo_medidor_rank) !== null) {
          meta.append(create("span", "pill over", `Reparo #${module.fila_reparo_medidor_rank}`));
        }
        if (number(module.fila_experiencia_rank) !== null) {
          meta.append(create("span", "pill", `Experiência #${module.fila_experiencia_rank}`));
        }
        if (number(module.fila_investigacao_custo_rank) !== null) {
          meta.append(create("span", "pill", `Custo contábil #${module.fila_investigacao_custo_rank}`));
        }
      } else {
        meta.append(create("span", "pill", `Prioridade #${module.prioridade_rank ?? "N/D"}`));
      }
      const interactionQuality = number(module.nota_qualidade_interacao_0a100);
      const interactionOpportunity = number(module.nota_oportunidade_interacao_0a100);
      meta.append(create(
        "span",
        `pill ${interactionQuality === null ? "" : interactionQuality >= 80 ? "ok" : "over"}`.trim(),
        `Qualidade adjudicada ${formatScore(interactionQuality)}`,
      ));
      if (interactionOpportunity !== null) {
        meta.append(create(
          "span",
          "pill",
          `Oportunidades adjudicadas ${formatScore(interactionOpportunity)}`,
        ));
      }
      const gateCompliance = number(module.gate_oportunidade_conformidade_pct);
      if (gateCompliance !== null) {
        meta.append(create("span", "pill ok", `Declaração ${formatPercent(gateCompliance, true)}`));
      }
      const opportunityPrecision = number(module.precisao_oportunidade);
      const opportunityCoverage = number(module.cobertura_oportunidade);
      const opportunityBalanced = number(module.acuracia_balanceada_oportunidade);
      if (opportunityPrecision !== null) {
        meta.append(create("span", "pill", `Precisão ${formatPercent(opportunityPrecision, true)}`));
      }
      if (opportunityCoverage !== null) {
        meta.append(create("span", "pill", `Cobertura ${formatPercent(opportunityCoverage, true)}`));
      }
      if (opportunityBalanced !== null) {
        meta.append(create("span", "pill", `Balanceada ${formatPercent(opportunityBalanced, true)}`));
      }
      const canonicalBalanced = number(module.acuracia_balanceada_integracao_canonica);
      if (canonicalBalanced !== null) {
        meta.append(create("span", "pill", `Integração ${formatPercent(canonicalBalanced, true)}`));
      }
      if (module.cobertura_integracao_completa !== null && module.cobertura_integracao_completa !== undefined) {
        meta.append(create(
          "span",
          `pill ${module.cobertura_integracao_completa ? "ok" : "over"}`,
          module.cobertura_integracao_completa ? "Cobertura completa" : "Cobertura incompleta",
        ));
      }
      if (module.cobertura_avaliativa_completa !== null && module.cobertura_avaliativa_completa !== undefined) {
        meta.append(create(
          "span",
          `pill ${module.cobertura_avaliativa_completa ? "ok" : "over"}`,
          module.cobertura_avaliativa_completa ? "Cobertura completa" : "Cobertura incompleta",
        ));
      }
      const bar = create("div", "bar");
      const fill = create("span");
      fill.style.setProperty("--width", `${clamp(moduleScore || 0)}%`);
      fill.style.setProperty("--bar-color", scoreColor(moduleScore));
      bar.append(fill);
      const stats = create("div", "module-stats");
      const values = [
        ["Turnos", INTEGER.format(module.turnos_detectados || 0)],
        ["Chamadas observadas", INTEGER.format(module.chamadas_detectadas || 0)],
        ["Qualidade", formatScore(interactionQuality)],
        ["Critérios válidos", INTEGER.format(module.denominador_qualidade_interacao || 0)],
        [hasIndependentPriorityQueues() ? "Custo contábil" : "Custo", formatTokens(module.tokens_totais_atribuidos_fracionados)],
        [hasIndependentPriorityQueues() ? "Rateio" : "Parcela", formatPercent(module.participacao_tokens_fracionados_pct, true)],
      ];
      for (const [label, value] of values) {
        const stat = create("div", "module-stat");
        stat.append(create("span", "", label), create("strong", "", value));
        stats.append(stat);
      }
      const details = document.createElement("details");
      details.append(create("summary", "", "Diagnóstico e evidências"));
      details.append(create("p", "", module.principais_problemas_de_ativacao || "Nenhum problema específico registrado."));
      if (instrumentationFailure) {
        details.append(create("p", "", "A nota foi bloqueada: houve atividade avaliativa esperada, mas o recibo obrigatório estava ausente, incompleto ou duplicado. Isso nunca é convertido em N/D."));
      } else if (notApplicable) {
        details.append(create("p", "", "O módulo respondeu com recibo completo e declarou explicitamente que nenhuma de suas operações era aplicável nesta sessão."));
      } else if (indeterminate) {
        details.append(create("p", "", "O módulo foi avaliado, mas a evidência não permite decidir aplicabilidade ou desempenho sem fabricar uma nota."));
      } else if (["evidencia_insuficiente", "sem_evidencia"].includes(module.aplicabilidade_avaliacao)) {
        details.append(create("p", "", "A nota permanece N/D: confiança do detector e latência exposta não substituem evidência de calibração ou de efeito."));
      }
      if (module.unidades_avaliativas_obrigatorias !== null && module.unidades_avaliativas_obrigatorias !== undefined) {
        details.append(create(
          "p",
          "",
          `Cobertura fail-closed: ${INTEGER.format(module.unidades_avaliativas_obrigatorias || 0)} atividade(s) esperada(s), ${INTEGER.format(module.recibos_cobertura_completos || 0)} recibo(s) completo(s), ${INTEGER.format(module.recibos_cobertura_ausentes || 0)} ausente(s), ${INTEGER.format(module.recibos_cobertura_incompletos || 0)} incompleto(s) e ${INTEGER.format(module.recibos_cobertura_duplicados || 0)} duplicado(s). Aplicáveis: ${INTEGER.format(module.unidades_avaliativas_aplicaveis || 0)}; não aplicáveis: ${INTEGER.format(module.unidades_avaliativas_nao_aplicaveis || 0)}; indeterminadas: ${INTEGER.format(module.unidades_avaliativas_indeterminadas || 0)}.`,
        ));
      }
      if ((module.dimensoes_semanticas_avaliadas || 0) > 0) {
        details.append(create(
          "p",
          "",
          `Auditoria semântica: ${INTEGER.format(module.dimensoes_semanticas_avaliadas)} dimensão(ões) avaliadas; ${INTEGER.format(module.dimensoes_semanticas_inadequadas || 0)} inadequada(s).`,
        ));
      }
      if ((module.avaliacoes_qualidade_recebidas || 0) > 0) {
        details.append(create(
          "p",
          "",
          `Qualidade por interação: ${INTEGER.format(module.avaliacoes_qualidade_pontuaveis || 0)} de ${INTEGER.format(module.avaliacoes_qualidade_recebidas || 0)} avaliação(ões) entram nos denominadores; ${INTEGER.format(module.avaliacoes_qualidade_pendentes || 0)} pendente(s), ${INTEGER.format(module.denominador_qualidade_interacao || 0)} critério(s) de qualidade e ${INTEGER.format(module.denominador_oportunidade_qualitativa || 0)} oportunidade(s) pontuável(is), incluindo ${INTEGER.format(module.oportunidades_qualitativas_perdidas || 0)} perdida(s).`,
        ));
      } else {
        details.append(create(
          "p",
          "",
          "Qualidade por interação não adjudicada. Os efeitos operacionais abaixo não substituem avaliação de qualidade.",
        ));
      }
      if (module.nota_conformidade_operacional_0a100 !== undefined) {
        details.append(create(
          "p",
          "",
          `Conformidade operacional: ${formatScore(module.nota_conformidade_operacional_0a100)} em ${INTEGER.format(module.efeitos_conformidade_operacional_avaliaveis || 0)} efeito(s). Esta medida permanece separada da qualidade por interação.`,
        ));
      }
      if (module.gate_oportunidade_preparos !== null && module.gate_oportunidade_preparos !== undefined) {
        details.append(create(
          "p",
          "",
          `Declaração do gate: ${INTEGER.format(module.gate_oportunidade_decisoes_validas || 0)}/${INTEGER.format(module.gate_oportunidade_preparos || 0)} preparos declarados; ${INTEGER.format(module.gate_oportunidade_violacoes || 0)} violação(ões) estruturais. Isso mede preenchimento, não acerto.`,
        ));
      }
      if (module.avaliacoes_oportunidade_recebidas !== null && module.avaliacoes_oportunidade_recebidas !== undefined) {
        details.append(create(
          "p",
          "",
          `Elegibilidade objetiva: ${INTEGER.format(module.avaliacoes_oportunidade_pontuaveis || 0)} caso(s) pontuável(is), ${INTEGER.format(module.avaliacoes_oportunidade_indeterminadas || 0)} indeterminado(s). Matriz: VP ${INTEGER.format(module.verdadeiros_positivos || 0)}, VN ${INTEGER.format(module.verdadeiros_negativos || 0)}, FP ${INTEGER.format(module.falsos_positivos || 0)}, FN ${INTEGER.format(module.falsos_negativos || 0)}.`,
        ));
      }
      if (module.avaliacoes_integracao_recebidas !== null && module.avaliacoes_integracao_recebidas !== undefined) {
        details.append(create(
          "p",
          "",
          `Integração canônica: ${INTEGER.format(module.unidades_sidequest_observadas || 0)} atividade(s), ${INTEGER.format(module.avaliacoes_integracao_recebidas || 0)} recibo(s) completo(s), ${INTEGER.format(module.recibos_integracao_ausentes || 0)} ausente(s), ${INTEGER.format(module.recibos_integracao_incompletos || 0)} incompleto(s) e ${INTEGER.format(module.recibos_integracao_duplicados || 0)} replay(s). Casos pontuáveis únicos: ${INTEGER.format(module.avaliacoes_integracao_pontuaveis || 0)}; não pontuáveis: ${INTEGER.format(module.avaliacoes_integracao_nao_pontuaveis || 0)}. Matriz: VP ${INTEGER.format(module.verdadeiros_positivos || 0)}, VN ${INTEGER.format(module.verdadeiros_negativos || 0)}, FP ${INTEGER.format(module.falsos_positivos || 0)}, FN ${INTEGER.format(module.falsos_negativos || 0)}.`,
        ));
      }
      if (hasIndependentPriorityQueues()) {
        details.append(create(
          "p",
          "",
          "O custo exibido é uma atribuição contábil por rateio igual entre módulos-pai observados no turno. Ele serve para reconciliação e triagem de investigação; não demonstra custo causal e não altera as filas de experiência ou reparo.",
        ));
      } else if (module.custo_exposto_participa_prioridade === false) {
        details.append(create("p", "", "O custo exibido é exposição não causal e não participa da prioridade."));
      }
      if (module.justificativa_prioridade) details.append(create("p", "", module.justificativa_prioridade));
      const release = state.releases.find((item) => item.module_id === module.modulo
        && item.implementation_version === module.versao_implementacao
        && item.evaluation_version === module.versao_avaliacao);
      if (release) details.append(create("p", "release-note", `Release ${release.effective_date} · ${release.source_revision}: ${release.reason}`));
      if (Array.isArray(module.subcapacidades) && module.subcapacidades.length) {
        const list = create("ul", "capability-list");
        for (const capability of module.subcapacidades) {
          const item = create("li");
          item.append(
            create("strong", "", friendlyModuleName(capability.capability_id)),
            create("span", "", ` · ${capability.eventos_observados} evento(s), ${capability.ativacoes_observadas} ativação(ões) — ${capability.responsabilidade}`),
          );
          list.append(item);
        }
        details.append(list);
      }
      card.append(header, description, meta, bar, stats, details);
      container.append(card);
    }
  }

  function selectField(row, field, options, label) {
    const wrapper = create("div", "field");
    const id = `feedback-${row.tipo}-${row.item}-${field}`;
    const fieldLabel = create("label", "", label);
    fieldLabel.htmlFor = id;
    const select = document.createElement("select");
    select.id = id;
    select.dataset.feedbackKey = feedbackKey(row);
    select.dataset.feedbackField = field;
    for (const [value, text] of options) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      option.selected = String(state.feedback[feedbackKey(row)]?.[field] ?? "") === String(value);
      select.append(option);
    }
    wrapper.append(fieldLabel, select);
    return wrapper;
  }

  function renderFeedback() {
    const globals = state.feedbackRows.filter((row) => row.tipo === "global");
    const modules = state.feedbackRows.filter((row) => row.tipo === "modulo");
    const globalContainer = $("#globalFeedback");
    globalContainer.replaceChildren();
    for (const row of globals) {
      const wrapper = create("div", "global-question");
      const label = create("label", "", row.rotulo);
      const id = `feedback-global-${row.item}`;
      label.htmlFor = id;
      const select = document.createElement("select");
      select.id = id;
      select.dataset.feedbackKey = feedbackKey(row);
      select.dataset.feedbackField = "nota_1a5";
      const options = [
        ["", "Não avaliado"],
        ["1", "1 · Muito ruim"],
        ["2", "2 · Ruim"],
        ["3", "3 · Adequado"],
        ["4", "4 · Bom"],
        ["5", "5 · Excelente"],
      ];
      for (const [value, text] of options) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        option.selected = String(state.feedback[feedbackKey(row)]?.nota_1a5 ?? "") === value;
        select.append(option);
      }
      wrapper.append(label, select);
      globalContainer.append(wrapper);
    }

    const moduleContainer = $("#moduleFeedback");
    moduleContainer.replaceChildren();
    for (const row of modules) {
      const wrapper = create("article", "module-question");
      const name = create("div", "question-name");
      name.append(create("strong", "", row.rotulo), create("small", "", friendlyModuleName(row.item)));
      wrapper.append(name);
      wrapper.append(selectField(row, "observado", [
        ["", "Não informado"], ["sim", "Sim"], ["nao", "Não percebi"], ["incerto", "Incerto"],
      ], "Percebeu?"));
      wrapper.append(selectField(row, "ativacao_menos2a2", [
        ["", "N/D"], ["-2", "Muito pouca"], ["-1", "Pouca"], ["0", "Adequada"], ["1", "Excessiva"], ["2", "Muito excessiva"],
      ], "Ativação"));
      wrapper.append(selectField(row, "nota_1a5", [
        ["", "N/D"], ["1", "1 · Muito ruim"], ["2", "2 · Ruim"], ["3", "3 · Adequado"], ["4", "4 · Bom"], ["5", "5 · Excelente"],
      ], "Resultado"));
      wrapper.append(selectField(row, "impacto_menos2a2", [
        ["", "N/D"], ["-2", "Muito negativo"], ["-1", "Negativo"], ["0", "Neutro"], ["1", "Positivo"], ["2", "Muito positivo"],
      ], "Impacto"));
      const commentField = create("div", "field");
      const id = `feedback-${row.item}-comentario`;
      const label = create("label", "", "Comentário");
      label.htmlFor = id;
      const textarea = document.createElement("textarea");
      textarea.id = id;
      textarea.rows = 1;
      textarea.placeholder = "Momento ou percepção opcional";
      textarea.value = state.feedback[feedbackKey(row)]?.comentario || "";
      textarea.dataset.feedbackKey = feedbackKey(row);
      textarea.dataset.feedbackField = "comentario";
      commentField.append(label, textarea);
      wrapper.append(commentField);
      moduleContainer.append(wrapper);
    }
  }

  function loadStoredManifestations() {
    try {
      const value = JSON.parse(localStorage.getItem(manifestationStorageKey()) || "[]");
      state.localManifestations = Array.isArray(value) ? value : [];
    } catch (_error) {
      state.localManifestations = [];
    }
  }

  function renderInteractionFeedback() {
    const select = $("#manifestationInteraction");
    select.replaceChildren();
    for (const interaction of state.interactions) {
      if (!interaction.interaction_ref) continue;
      const option = document.createElement("option");
      option.value = interaction.interaction_ref;
      option.textContent = `${interaction.interaction_ref} · ${interaction.class || "ON"}`;
      select.append(option);
    }
    const all = [...state.manifestations, ...state.localManifestations];
    $("#manifestationCount").textContent = INTEGER.format(all.length);
    const list = $("#manifestationList");
    list.replaceChildren();
    for (const item of all) {
      const card = create("article", "manifestation-card");
      const stateLabel = item.adjudication?.state || "pendente";
      card.append(
        create("strong", "", `${item.interaction_ref} · ${item.perceived_type}`),
        create("span", "pill", stateLabel),
        create("p", "", item.original_text),
      );
      list.append(card);
    }
    if (!all.length) list.append(create("p", "empty-state", "Nenhuma manifestação registrada nesta sessão."));
  }

  async function addManifestation(event) {
    event.preventDefault();
    const reference = $("#manifestationInteraction").value;
    const textValue = $("#manifestationText").value.trim();
    if (!reference || !textValue) return;
    const feedbackId = `feedback-${(await sha256(`${reference}\0${textValue}`)).slice(0, 20)}`;
    const item = {
      feedback_id: feedbackId,
      interaction_ref: reference,
      recorded_at: new Date().toISOString(),
      original_text: textValue,
      perceived_type: $("#manifestationType").value,
      expectation: $("#manifestationExpectation").value.trim() || null,
      observation: null,
      perceived_impact: $("#manifestationImpact").value || null,
      player_module_id: null,
      player_capability_id: null,
      system_suggestion: null,
      adjudication: { state: "pendente", reason: null },
    };
    const existing = state.localManifestations.findIndex((value) => value.feedback_id === feedbackId);
    if (existing >= 0) state.localManifestations[existing] = item;
    else state.localManifestations.push(item);
    localStorage.setItem(manifestationStorageKey(), JSON.stringify(state.localManifestations));
    $("#interactionFeedbackForm").reset();
    renderInteractionFeedback();
    renderScore();
    showToast("Manifestação salva neste navegador.");
  }

  function exportManifestations() {
    const value = {
      schema_narrative_interactions: 1,
      session: state.sessionEntry.sessao_id,
      interactions: state.interactions,
      player_feedback: [...state.manifestations, ...state.localManifestations],
    };
    const blob = new Blob([JSON.stringify(value, null, 2), "\n"], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `manifestacoes-jogador-sessao-${state.sessionEntry.sessao_id}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    showToast("Manifestações exportadas em JSON.");
  }

  function handleFeedbackInput(event) {
    const target = event.target.closest("[data-feedback-key]");
    if (!target) return;
    const key = target.dataset.feedbackKey;
    const field = target.dataset.feedbackField;
    state.feedback[key][field] = target.value;
    saveFeedback();
    renderScore();
    renderAxes();
    renderInsights();
    renderModules();
  }

  function exportFeedback() {
    const rows = state.feedbackRows.map((row) => state.feedback[feedbackKey(row)] || row);
    const blob = new Blob(["\uFEFF", toCSV(rows)], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `feedback-jogador-sessao-${state.sessionEntry.sessao_id}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    showToast("Feedback exportado em CSV.");
  }

  async function importFeedback(file) {
    const incoming = parseCSV(await file.text());
    const incomingByKey = Object.fromEntries(incoming.map((row) => [feedbackKey(row), row]));
    for (const row of state.feedbackRows) {
      const key = feedbackKey(row);
      if (incomingByKey[key]) state.feedback[key] = { ...row, ...incomingByKey[key] };
    }
    saveFeedback();
    renderFeedback();
    renderAllDataViews();
    showToast("Feedback importado e salvo localmente.");
  }

  function resetFeedback() {
    if (!window.confirm("Limpar todas as respostas locais desta sessão?")) return;
    localStorage.removeItem(storageKey());
    loadStoredFeedback();
    renderFeedback();
    renderAllDataViews();
    $("#saveStatus").textContent = "Respostas locais removidas.";
  }

  let toastTimer;
  function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 2200);
  }

  function renderAllDataViews() {
    renderHeader();
    renderAxes();
    renderTrend();
    renderMetrics();
    renderInsights();
    renderModules();
  }

  async function loadSession(sessionId) {
    const entry = state.index.sessoes.find((item) => item.sessao_id === sessionId);
    if (!entry) throw new Error(`sessão ${sessionId} não encontrada no índice`);
    state.sessionEntry = entry;
    const base = `../sessions/${entry.caminho}`;
    const [scorecard, moduleSummary] = await Promise.all([
      fetchJSON(`${base}/scorecard.json`),
      fetchJSON(`${base}/resumo-modulos.json`),
    ]);
    state.scorecard = scorecard;
    state.modules = moduleSummary.modulos || [];
    $("#moduleSort").value = hasIndependentPriorityQueues() ? "experiencia" : "prioridade";
    if (entry.serie_avaliacao === "modules-v2") {
      const [interactionData, manifestationData] = await Promise.all([
        fetchJSON(`${base}/interacoes.json`),
        fetchJSON(`${base}/manifestacoes-jogador.json`),
      ]);
      state.interactions = interactionData.interactions || [];
      state.manifestations = manifestationData.player_feedback || [];
      state.feedbackRows = [];
      state.feedback = {};
      loadStoredManifestations();
      $("#legacyFeedbackSection").hidden = true;
      $("#interactionFeedbackSection").hidden = false;
      renderInteractionFeedback();
    } else {
      state.feedbackRows = parseCSV(await fetchText(`${base}/feedback-jogador.csv`));
      state.interactions = [];
      state.manifestations = [];
      state.localManifestations = [];
      loadStoredFeedback();
      $("#legacyFeedbackSection").hidden = false;
      $("#interactionFeedbackSection").hidden = true;
      renderFeedback();
    }
    renderAllDataViews();
    $("#main")?.removeAttribute("hidden");
    $("#topo").hidden = false;
  }

  async function initialize() {
    try {
      const [sessionIndex, releaseHistory] = await Promise.all([
        fetchJSON(SESSION_INDEX),
        fetchJSON("../module-releases.json"),
      ]);
      state.index = sessionIndex;
      state.releases = releaseHistory.releases || [];
      const sessions = state.index.sessoes || [];
      if (!sessions.length) throw new Error("o índice não contém sessões avaliadas");
      const select = $("#sessionSelect");
      for (const session of sessions) {
        const option = document.createElement("option");
        option.value = session.sessao_id;
        option.textContent = `Sessão ${session.sessao_id}`;
        select.append(option);
      }
      const latest = sessions[sessions.length - 1];
      select.value = latest.sessao_id;
      await loadSession(latest.sessao_id);
      $("#loadingState").hidden = true;
      $("#topo").hidden = false;
    } catch (error) {
      $("#loadingState").hidden = true;
      $("#errorState").hidden = false;
      $("#errorMessage").textContent = error instanceof Error ? error.message : String(error);
    }
  }

  $("#sessionSelect").addEventListener("change", (event) => loadSession(event.target.value));
  $("#trendMetric").addEventListener("change", renderTrend);
  $("#moduleSearch").addEventListener("input", renderModules);
  $("#activationFilter").addEventListener("change", renderModules);
  $("#moduleSort").addEventListener("change", renderModules);
  $("#feedbackForm").addEventListener("input", handleFeedbackInput);
  $("#feedbackForm").addEventListener("change", handleFeedbackInput);
  $("#exportFeedback").addEventListener("click", exportFeedback);
  $("#resetFeedback").addEventListener("click", resetFeedback);
  $("#importFeedback").addEventListener("change", (event) => {
    const [file] = event.target.files || [];
    if (file) importFeedback(file).catch((error) => showToast(`Falha ao importar: ${error.message}`));
    event.target.value = "";
  });
  $("#interactionFeedbackForm").addEventListener("submit", addManifestation);
  $("#exportManifestations").addEventListener("click", exportManifestations);
  $("#resetManifestations").addEventListener("click", () => {
    if (!window.confirm("Limpar as manifestações locais desta sessão?")) return;
    localStorage.removeItem(manifestationStorageKey());
    state.localManifestations = [];
    renderInteractionFeedback();
    renderScore();
  });

  initialize();
})();
