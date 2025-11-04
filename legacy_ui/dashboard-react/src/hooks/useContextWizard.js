import { useCallback, useMemo, useState } from "react";
import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers = config.headers || {};
    if (!config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      const message = data?.detail || data?.message || error.message || "Error desconocido";
      return Promise.reject(new Error(`(${status}) ${message}`));
    }
    if (error.request) {
      return Promise.reject(new Error("Sin respuesta del servidor. Verifica tu conexión."));
    }
    return Promise.reject(error);
  }
);

export const useContextWizard = (companyId) => {
  const [questions, setQuestions] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState({});
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [initialContext, setInitialContext] = useState("");

  const currentQuestion = useMemo(() => {
    if (!questions.length) return null;
    return questions[currentIdx];
  }, [questions, currentIdx]);

  const loadQuestions = useCallback(
    async (contextText, count = 5) => {
      setLoadingQuestions(true);
      try {
        setInitialContext(contextText);
        const { data } = await apiClient.post("/companies/context/questions", {
          company_id: companyId,
          context: contextText,
          count,
        });
        setQuestions(data?.questions || []);
        setCurrentIdx(0);
        setAnswers({});
      } finally {
        setLoadingQuestions(false);
      }
    },
    [companyId]
  );

  const saveAnswer = useCallback(
    (value) => {
      if (!currentQuestion) return;
      setAnswers((prev) => ({
        ...prev,
        [currentQuestion.question]: value,
      }));
    },
    [currentQuestion]
  );

  const nextQuestion = useCallback(() => {
    setCurrentIdx((idx) => Math.min(idx + 1, questions.length - 1));
  }, [questions.length]);

  const prevQuestion = useCallback(() => {
    setCurrentIdx((idx) => Math.max(idx - 1, 0));
  }, []);

  const hasNext = questions.length > 0 && currentIdx < questions.length - 1;
  const hasPrev = currentIdx > 0;

  const finalize = useCallback(
    async (source = "wizard") => {
      setSubmitting(true);
      try {
        const orderedQuestions = questions.map((q) => q.question);
        const answerText = orderedQuestions
          .map((question) => {
            const response = answers[question] || "";
            return `${question}: ${response}`;
          })
          .join(". ");

        const finalText = [initialContext, answerText].filter(Boolean).join(". ");

        const { data } = await apiClient.post("/companies/context/analyze", {
          company_id: companyId,
          text: finalText,
          source,
        });

        try {
          await apiClient.post("/users/mark_onboarding", {});
          localStorage.setItem("onboarding_completed", "true");
        } catch (err) {
          console.warn("No se pudo marcar el onboarding como completado", err);
        }

        setAnalysisResult(data);
        try {
          localStorage.setItem("company_context", JSON.stringify(data.analysis));
        } catch (err) {
          console.warn("No se pudo guardar el contexto en localStorage", err);
        }
        return data;
      } finally {
        setSubmitting(false);
      }
    },
    [answers, companyId, initialContext, questions]
  );

  return {
    questions,
    currentQuestion,
    currentIdx,
    answers,
    loadingQuestions,
    submitting,
    analysisResult,
    loadQuestions,
    saveAnswer,
    nextQuestion,
    prevQuestion,
    hasNext,
    hasPrev,
    finalize,
  };
};
