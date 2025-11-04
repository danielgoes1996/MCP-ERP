import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { Sparkles, Wand2 } from "lucide-react";

const baseButton =
  "inline-flex items-center justify-center px-4 py-2 rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2";

export const ContextQuestionCard = ({
  question,
  initialValue = "",
  onAnswer,
  onNext,
  onPrev,
  hasNext,
  hasPrev,
  step,
  totalSteps,
  isLast,
}) => {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue, question]);

  const handleSave = () => {
    onAnswer(value);
  };

  const handleNext = () => {
    onAnswer(value);
    onNext();
  };

  return (
    <motion.div
      key={question}
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -24 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="bg-white border border-slate-200 rounded-xl shadow-lg">
        <div className="p-6 border-b border-slate-200/80">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
            <Sparkles className="h-4 w-4 text-amber-400" />
            Paso {step} de {totalSteps}
          </div>
          <h3 className="mt-3 text-2xl font-semibold text-slate-900">{question}</h3>
          <p className="mt-2 text-sm text-slate-600">
            Comparte detalles operativos; la IA usará esta información para afinar la clasificación bancaria.
          </p>
        </div>
        <div className="p-6 space-y-6">
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Escribe tu respuesta aquí..."
            className="w-full min-h-[140px] rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button
              onClick={onPrev}
              disabled={!hasPrev}
              className={`${baseButton} border border-slate-300 text-slate-700 bg-white hover:bg-slate-100 disabled:opacity-50`}
            >
              Anterior
            </button>
            <div className="flex items-center gap-2">
              <button
                onClick={handleSave}
                className={`${baseButton} border border-emerald-500 text-emerald-700 bg-white hover:bg-emerald-50`}
              >
                Guardar
              </button>
              <button
                onClick={handleNext}
                className={`${baseButton} bg-emerald-500 text-white hover:bg-emerald-600`}
              >
                {isLast ? "Finalizar" : "Siguiente"}
                <Wand2 className="ml-2 h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default ContextQuestionCard;
