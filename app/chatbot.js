import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Bot,
  Loader2,
  MessageCircle,
  RefreshCcw,
  Send,
  User,
} from "lucide-react";

const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || "http://localhost:8000";

function getPathValue() {
  return window.location.pathname || "/";
}

function normalizeAgentType(value) {
  return value === "product" ? "product" : "chat";
}

function getInitialTenantSlug() {
  const path = getPathValue();

  const slashMatch = path.match(/^\/chat\/([^/]+)/);
  if (slashMatch?.[1]) return slashMatch[1];

  const underscoreMatch = path.match(/^\/chat_([^/]+)/);
  if (underscoreMatch?.[1]) return underscoreMatch[1];

  return localStorage.getItem("public_chat_tenant_slug") || "public";
}

function buildWelcomeText() {
   return "Loading assistant...";
}

async function getTenantActiveAgentType(tenantSlug) {
  try {
    const res = await fetch(
      `${API_BASE_URL}/tenant/active-agent-type/${encodeURIComponent(tenantSlug)}`
    );

    const data = await res.json().catch(() => null);

    if (!res.ok || !data?.success) {
      return "chat";
    }

    return normalizeAgentType(data.active_agent_type || data.agent_type || "chat");
  } catch {
    return "chat";
  }
}

async function resolveChatRoute() {
  const path = getPathValue();

  if (path.startsWith("/chat_") || path.startsWith("/chat/")) {
    const tenantSlug = getInitialTenantSlug();
    const agentType = await getTenantActiveAgentType(tenantSlug);

    localStorage.setItem("public_chat_tenant_slug", tenantSlug);
    localStorage.setItem("public_chat_agent_type", agentType);

    return {
      tenantSlug,
      agentType,
      chatApiPath: path,
    };
  }

  const publicName = path.replace(/^\/+/, "").split("/")[0];

  const res = await fetch(
    `${API_BASE_URL}/public-link/resolve/${encodeURIComponent(publicName)}`
  );

  const data = await res.json().catch(() => null);

  if (!res.ok || !data?.success) {
    throw new Error(data?.detail || "Public link not found.");
  }

  const tenantSlug = data.tenant_slug || "public";
  const agentType = normalizeAgentType(
    data.active_agent_type || data.agent_type || data.type || "chat"
  );
  const chatApiPath = data.redirect_path || data.target_path || `/chat_${tenantSlug}`;

  localStorage.setItem("public_chat_tenant_slug", tenantSlug);
  localStorage.setItem("public_chat_agent_type", agentType);

  return {
    tenantSlug,
    agentType,
    chatApiPath,
  };
}

function makeSessionId(tenantSlug, agentType = "chat") {
  const key = `agent_chat_session_id_${agentType}_${tenantSlug}`;
  const old = localStorage.getItem(key);
  if (old) return old;

  const id = `session_${agentType}_${tenantSlug}_${Date.now()}_${Math.random()
    .toString(16)
    .slice(2)}`;
  localStorage.setItem(key, id);
  return id;
}

function timeNow() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(value || "").trim());
}

function toArray(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return [value].filter(Boolean);
}

function getChatAssets(result) {
  const images = [
    ...toArray(result?.images),
    ...toArray(result?.image_urls),
    ...toArray(result?.assets?.images),
  ];

  const links = [
    ...toArray(result?.links),
    ...toArray(result?.link_urls),
    ...toArray(result?.assets?.links),
    ...toArray(result?.sources),
    ...toArray(result?.assets?.sources),
  ];

  return {
    images: [...new Set(images.map((item) => String(item).trim()).filter(Boolean))],
    links: [...new Set(links.map((item) => String(item).trim()).filter(Boolean))],
  };
}

function isValidImageUrl(url) {
  return /^https?:\/\//i.test(String(url || ""));
}

function isValidLinkUrl(url) {
  return /^https?:\/\//i.test(String(url || ""));
}

function getProductBotText(result) {
  if (Array.isArray(result?.responses) && result.responses.length) {
    return result.responses.join("\n\n");
  }

  return result?.answer || result?.message || "I could not create an answer.";
}

// Quick reply buttons are tenant-specific.
// Keep this list in sync with SPECIAL_SALES_TENANT_SLUGS in product_query_bot.py.
const PRODUCT_CHOICE_BUTTON_TENANT_SLUGS = ["desipos"];

function shouldShowProductChoiceButtons(text = "", agentType = "chat", tenantSlug = "") {
  const normalizedTenant = String(tenantSlug || "").trim().toLowerCase();

  return (
    agentType === "product" &&
    PRODUCT_CHOICE_BUTTON_TENANT_SLUGS.includes(normalizedTenant) &&
    text.includes("Model Number") &&
    text.includes("Sales Enquiry")
  );
}

export default function ChatBot() {
  const bottomRef = useRef(null);

  const [tenantSlug, setTenantSlug] = useState(() => getInitialTenantSlug());
  const [agentType, setAgentType] = useState("chat");
  const [chatApiPath, setChatApiPath] = useState(() => getPathValue());
  const [routeReady, setRouteReady] = useState(false);

  const [sessionId, setSessionId] = useState(() =>
    makeSessionId(getInitialTenantSlug(), "chat")
  );

  const customerKey = `public_chat_customer_${agentType}_${tenantSlug}`;

  const savedCustomer = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem(customerKey) || "{}");
    } catch {
      return {};
    }
  }, [customerKey]);

  const [customerName, setCustomerName] = useState(savedCustomer.name || "");
  const [customerEmail, setCustomerEmail] = useState(savedCustomer.email || "");
  const [step, setStep] = useState(
    savedCustomer.name && savedCustomer.email ? "chat" : "name"
  );

  const [message, setMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");

  const [messages, setMessages] = useState([
    {
      id: "welcome_loading",
      role: "bot",
      text: "Loading assistant...",
      time: timeNow(),
    },
  ]);

  const canSend = useMemo(
    () => message.trim() && !isSending && routeReady,
    [message, isSending, routeReady]
  );

  useEffect(() => {
    async function setupRoute() {
      try {
        const resolved = await resolveChatRoute();

        setTenantSlug(resolved.tenantSlug);
        setAgentType(resolved.agentType);
        setChatApiPath(resolved.chatApiPath);

        const newSessionId = makeSessionId(
          resolved.tenantSlug,
          resolved.agentType
        );
        setSessionId(newSessionId);

        const welcomeUrl =
          resolved.agentType === "product"
            ? `${API_BASE_URL}/product-query/public-chat/${resolved.tenantSlug}`
            : `${API_BASE_URL}${resolved.chatApiPath}`;

        const welcomeBody =
          resolved.agentType === "product"
            ? {
                query: "__welcome__",
                session_id: newSessionId,
              }
            : {
                message: "__welcome__",
                session_id: newSessionId,
                top_k: 5,
              };

        let welcomeText = buildWelcomeText();

        try {
          const welcomeRes = await fetch(welcomeUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(welcomeBody),
          });

          const welcomeData = await welcomeRes.json().catch(() => null);

          if (welcomeRes.ok) {
            welcomeText =
              resolved.agentType === "product"
                ? getProductBotText(welcomeData)
                : welcomeData?.answer || "Hi! How can I help you today?";

            if (welcomeData?.tenant_name) {
              localStorage.setItem("tenant_name", welcomeData.tenant_name);
            }
          } else {
            welcomeText =
              resolved.agentType === "product"
                ? "Hello, do you have a model number? Please choose Yes or No."
                : "Hi! How can I help you today?";
          }
        } catch {
          welcomeText =
            resolved.agentType === "product"
              ? "Hello, do you have a model number? Please choose Yes or No."
              : "Hi! How can I help you today?";
        }

        if (resolved.agentType === "product") {
          setStep("chat");
        }

        setMessages([
          {
            id: "welcome_dynamic",
            role: "bot",
            text: welcomeText,
            time: timeNow(),
          },
        ]);

        setRouteReady(true);
        setError("");
      } catch (err) {
        const msg = err.message || "Public chat link is invalid.";
        setError(msg);
        setRouteReady(false);
        setMessages((prev) => [
          ...prev,
          {
            id: `route_error_${Date.now()}`,
            role: "bot",
            text: msg,
            time: timeNow(),
            isError: true,
          },
        ]);
      }
    }

    setupRoute();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const saveCustomerLocal = (name, email) => {
    localStorage.setItem(customerKey, JSON.stringify({ name, email }));
  };

  const resetChat = () => {
    const key = `agent_chat_session_id_${agentType}_${tenantSlug}`;
    const id = `session_${agentType}_${tenantSlug}_${Date.now()}_${Math.random()
      .toString(16)
      .slice(2)}`;

    localStorage.setItem(key, id);
    localStorage.removeItem(customerKey);

    // Keep Redis/backend session flow clean: new session_id + fresh backend welcome.
    window.location.reload();
    return;
  };

  const addUserMessage = (text) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `u_${Date.now()}`,
        role: "user",
        text,
        time: timeNow(),
      },
    ]);
  };

  const addBotMessage = (text, isError = false, assets = {}) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `b_${Date.now()}_${Math.random()}`,
        role: "bot",
        text,
        time: timeNow(),
        isError,
        images: toArray(assets.images),
        links: toArray(assets.links),
      },
    ]);
  };

  const saveCustomerToBackend = async (email) => {
    try {
      await fetch(`${API_BASE_URL}/public-chat/customer/${tenantSlug}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `${
            agentType === "product" ? "Product bot" : "Chat bot"
          } customer registered from public chat`,
          session_id: sessionId,
          customer_name: customerName,
          customer_email: email,
          agent_type: agentType,
        }),
      });
    } catch {
      // Do not block the chat UI if only contact pre-save fails.
    }
  };

  const sendMessage = async (quickReplyText = "") => {
    const clean = String(quickReplyText || message).trim();
    if (!clean || isSending || !routeReady) return;

    addUserMessage(clean);
    setMessage("");
    setError("");

    if (step === "name") {
      setCustomerName(clean);
      setStep("email");
      addBotMessage("Thanks. Please share your email address.");
      return;
    }

    if (step === "email") {
      if (!isValidEmail(clean)) {
        addBotMessage("Please enter a valid email address.", true);
        return;
      }

      setCustomerEmail(clean);
      saveCustomerLocal(customerName, clean);
      await saveCustomerToBackend(clean);

      setStep("chat");
      addBotMessage(
        agentType === "product"
          ? "Thank you. Do you have model number? Choose: Yes / No"
          : "Thank you. How can I help you today?"
      );
      return;
    }

    try {
      setIsSending(true);

      const url =
        agentType === "product"
          ? `${API_BASE_URL}/product-query/public-chat/${tenantSlug}`
          : `${API_BASE_URL}${chatApiPath}`;

      const body =
        agentType === "product"
          ? {
              query: clean,
              session_id: sessionId,
              customer_name: customerName,
              customer_email: customerEmail,
            }
          : {
              message: clean,
              session_id: sessionId,
              top_k: 5,
              customer_name: customerName,
              customer_email: customerEmail,
            };

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const result = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(
          result?.detail || result?.message || `Chat failed: ${response.status}`
        );
      }

      if (result?.session_id && result.session_id !== sessionId) {
        const key = `agent_chat_session_id_${agentType}_${tenantSlug}`;
        localStorage.setItem(key, result.session_id);
        setSessionId(result.session_id);
      }

      const assets = getChatAssets(result);

      addBotMessage(
        agentType === "product"
          ? getProductBotText(result)
          : result?.answer || result?.message || "I could not create an answer.",
        false,
        assets
      );
    } catch (err) {
      const msg = err.message || "Something went wrong while chatting.";
      setError(msg);
      addBotMessage(msg, true);
    } finally {
      setIsSending(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <main className="mx-auto flex min-h-screen max-w-5xl flex-col px-3 py-4 sm:px-6">
        <div className="overflow-hidden rounded-3xl bg-white shadow-sm ring-1 ring-slate-200">
          <header className="flex items-center justify-between bg-purple-600 px-4 py-4 text-white sm:px-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => (window.location.href = "/")}
                className="rounded-full p-2 hover:bg-white/10"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>

              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-white/15">
                <MessageCircle className="h-6 w-6" />
              </div>

              <div>
                <h2 className="text-base font-bold sm:text-lg">
                  {agentType === "product"
                    ? "Product Assistant"
                    : "Chat Assistant"}
                </h2>
                <p className="text-xs text-purple-100">
                {agentType === "product"
                  ? "Product Bot"
                  : ""}
              </p>
              </div>
            </div>

            <button
              type="button"
              onClick={resetChat}
              className="inline-flex items-center gap-2 rounded-xl bg-white/10 px-3 py-2 text-xs font-bold hover:bg-white/20"
            >
              <RefreshCcw className="h-4 w-4" /> New Chat
            </button>
          </header>

          <section className="h-[calc(100vh-190px)] min-h-[520px] overflow-y-auto bg-[linear-gradient(135deg,#f8fafc_0%,#eef2ff_100%)] px-3 py-5 sm:px-6">
            <div className="space-y-4">
              {messages.map((item) => {
                const isUser = item.role === "user";

                return (
                  <div
                    key={item.id}
                    className={`flex items-end gap-2 ${
                      isUser ? "justify-end" : "justify-start"
                    }`}
                  >
                    {!isUser && (
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white text-purple-600 shadow-sm">
                        <Bot className="h-4 w-4" />
                      </div>
                    )}

                    <div
                      className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm sm:max-w-[70%] ${
                        isUser
                          ? "rounded-br-sm bg-purple-600 text-white"
                          : item.isError
                          ? "rounded-bl-sm border border-red-200 bg-red-50 text-red-700"
                          : "rounded-bl-sm bg-white text-slate-700"
                      }`}
                    >
                      <p
                    className={`whitespace-pre-wrap ${
                      agentType === "product" ? "font-mono text-[14px]" : ""
                    }`}
                  >
                    {item.text.split("\n").map((line, idx) => {
                      const isLink = line.startsWith("http://") || line.startsWith("https://");

                      if (isLink) {
                        return (
                          <a
                            key={idx}
                            href={line.trim()}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-600 underline break-all block"
                          >
                            {line}
                          </a>
                        );
                      }

                      return <div key={idx}>{line}</div>;
                    })}
                  </p>

                      {!isUser &&
                        shouldShowProductChoiceButtons(
                          item.text,
                          agentType,
                          tenantSlug
                        ) && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => sendMessage("1")}
                              disabled={isSending || !routeReady}
                              className="rounded-full border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700 hover:bg-purple-100 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              Model Number
                            </button>
                            <button
                              type="button"
                              onClick={() => sendMessage("2")}
                              disabled={isSending || !routeReady}
                              className="rounded-full border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700 hover:bg-purple-100 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              Sales Enquiry
                            </button>
                          </div>
                        )}

                      {!isUser && item.images?.length > 0 && (
                        <div className="chat-image-grid">
                          {item.images.filter(isValidImageUrl).map((url, index) => (
                            <a
                              key={`${url}-${index}`}
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                              className="chat-image-link"
                            >
                              <img
                                src={url}
                                alt={`Product ${index + 1}`}
                                className="chat-product-image"
                                loading="lazy"
                              />
                            </a>
                          ))}
                        </div>
                      )}

                      {!isUser && item.links?.length > 0 && (
                        <div className="chat-link-list">
                          {item.links.filter(isValidLinkUrl).map((url, index) => (
                            <a
                              key={`${url}-${index}`}
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                              className="chat-source-link"
                            >
                              View source {index + 1}
                            </a>
                          ))}
                        </div>
                      )}

                      <div
                        className={`mt-1 text-right text-[10px] ${
                          isUser ? "text-purple-100" : "text-slate-400"
                        }`}
                      >
                        {item.time}
                      </div>
                    </div>

                    {isUser && (
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-purple-600 text-white shadow-sm">
                        <User className="h-4 w-4" />
                      </div>
                    )}
                  </div>
                );
              })}

              {isSending && (
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" /> Assistant is
                  typing...
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </section>

          {error && (
            <div className="border-t border-red-100 bg-red-50 px-4 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <footer className="border-t border-slate-200 bg-white p-3 sm:p-4">
            <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2 focus-within:border-purple-400 focus-within:ring-2 focus-within:ring-purple-100">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  step === "name"
                    ? "Enter your name"
                    : step === "email"
                    ? "Enter your email"
                    : routeReady
                    ? agentType === "product"
                      ? "Type Yes / No, model number, or barcode..."
                      : "Type your message..."
                    : "Loading chat..."
                }
                rows={1}
                className="max-h-32 min-h-[42px] flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-slate-400"
              />

              <button
                type="button"
                onClick={sendMessage}
                disabled={!canSend}
                className="inline-flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl bg-purple-600 text-white shadow-sm hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSending ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <Send className="h-5 w-5" />
                )}
              </button>
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
