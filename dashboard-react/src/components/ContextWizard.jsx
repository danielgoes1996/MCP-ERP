import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, CheckCircle2, ArrowRight, Sparkles } from "lucide-react";
import { ContextQuestionCard } from "./ContextQuestionCard";
import { useContextWizard } from "../hooks/useContextWizard";
import { useToast } from "../ui";

const baseButton =
  "inline-flex items-center justify-center px-4 py-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2";

export const ContextWizard = ({ companyId, onCompleted }) => {
  const [initialDescription, setInitialDescription] = useState("");
  const [questionsLoaded, setQuestionsLoaded] = useState(false);
  const { show: showToast } = useToast();

  const {
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
  } = useContextWizard(companyId);

  const isLastStep = useMemo(() => {
    if (!questions.length) return false;
    return currentIdx === questions.length - 1;
  }, [currentIdx, questions]);

  useEffect(() => {
    if (analysisResult && onCompleted) {
      onCompleted(analysisResult);
    }
  }, [analysisResult, onCompleted]);

  const handleGenerateQuestions = async () => {
    if (!initialDescription.trim()) {
      showToast({ message: "Describe brevemente tu empresa antes de continuar", intent: "danger" });
      return;
    }

    try {
      await loadQuestions(initialDescription, 5);
      setQuestionsLoaded(true);
      showToast({ message: "Preguntas generadas con Claude", intent: "success" });
    } catch (error) {
      showToast({ message: error.message || "No fue posible generar preguntas", intent: "danger" });
    }
  };

  const handleFinalize = async () => {
    try {
      const result = await finalize("wizard");
      if (result) {
        showToast({ message: "Contexto actualizado correctamente", intent: "success" });
      }
    } catch (error) {
      showToast({ message: error.message || "Error analizando el contexto", intent: "danger" });
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-10 flex flex-col gap-6">
      <header className="max-w-4xl mx-auto text-center space-y-3">
        <div className="flex items-center justify-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
          <Sparkles className="h-5 w-5 text-amber-400" />
          Context Onboarding Wizard
        </div>
        <h1 className="text-3xl md:text-4xl font-semibold text-slate-900">
          Construyamos el perfil operativo de tu empresa
        </h1>
        <p className="text-slate-600 max-w-2xl mx-auto">
          Usemos IA para entender cómo funciona tu negocio y mejorar la clasificación contable de tus movimientos bancarios.
        </p>
      </header>

      {!questionsLoaded && !questions.length ? (
        <motion.div
          className="max-w-3xl mx-auto bg-white border border-slate-200 rounded-2xl shadow-lg p-8 space-y-6"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h2 className="text-2xl font-semibold text-slate-900 mb-2">¿Qué hace tu empresa?</h2>
          <p className="text-slate-600 text-sm">
            Escríbenos una breve descripción. Claude generará una serie de preguntas naturales para completar tu contexto.
          </p>
          <textarea
            value={initialDescription}
            onChange={(e) => setInitialDescription(e.target.value)}
            placeholder="Ej. Somos una comercializadora que compra abarrotes y los distribuye a tiendas locales..."
            className="w-full min-h-[160px] rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <div className="flex justify-end">
            <button
              onClick={handleGenerateQuestions}
              disabled={loadingQuestions}
              className={`${baseButton} bg-emerald-500 text-white hover:bg-emerald-600`}
            >
              {loadingQuestions ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generando preguntas...
                </>
              ) : (
                "Comenzar"
              )}
            </button>
          </div>
        </motion.div>
      ) : (
        <div className="max-w-4xl mx-auto w-full space-y-6">
          {currentQuestion ? (
            <ContextQuestionCard
              question={currentQuestion.question}
              initialValue={answers[currentQuestion.question]}
              onAnswer={saveAnswer}
              onNext={hasNext ? nextQuestion : handleFinalize}
              onPrev={hasPrev ? prevQuestion : () => {}}
              hasNext={hasNext}
              hasPrev={hasPrev}
              step={currentIdx + 1}
              totalSteps={questions.length}
              isLast={isLastStep}
            />
          ) : (
            <div className="bg-white border border-slate-200 rounded-2xl shadow-lg p-8 text-center space-y-4">
              <h3 className="text-xl font-semibold text-slate-900">
                ¡Listo! Analicemos tu contexto.
              </h3>
              <button
                onClick={handleFinalize}
                disabled={submitting}
                className={`${baseButton} bg-emerald-500 text-white hover:bg-emerald-600`}
              >
                {submitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analizando...
                  </>
                ) : (
                  "Generar resumen con IA"
                )}
              </button>
            </div>
          )}

          {analysisResult && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white border border-emerald-200 rounded-2xl shadow-md p-6 space-y-4"
            >
              <div className="flex items-center gap-2 text-emerald-600">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-semibold">Claude generó el contexto operativo</span>
              </div>
              <pre className="bg-emerald-50 text-emerald-900 rounded-lg p-4 text-xs max-h-64 overflow-auto">
                {JSON.stringify(analysisResult.analysis, null, 2)}
              </pre>
              <button
                className={`${baseButton} border border-emerald-500 text-emerald-700 bg-white hover:bg-emerald-50`}
                onClick={() => {
                  try {
                    localStorage.setItem("onboarding_completed", "true");
                  } catch (err) {
                    console.warn("No se pudo guardar la preferencia", err);
                  }
                  if (onCompleted) onCompleted(analysisResult);
                  window.location.href = "/banking/reconciliation";
                }}
              >
                Ir a Conciliación Bancaria
                <ArrowRight className="ml-2 h-4 w-4" />
              </button>
            </motion.div>
          )}
        </div>
      )}
    </div>
  );
};

export default ContextWizard;
