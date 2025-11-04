const { useState, useEffect, useMemo } = React;

const API_ROOT = '/api/v1';
const STEPS = {
  INTRO: 'intro',
  INTERVIEW: 'interview',
  REVIEW: 'review',
};

const DEFAULT_QUESTIONS = [
  { question: '¿Qué productos o servicios ofreces principalmente y cómo los entregas?' },
  { question: '¿Quiénes son tus clientes más importantes y cómo te contactan?' },
  { question: '¿A quién le compras insumos clave o cómo obtienes tu inventario?' },
  { question: '¿Con qué frecuencia realizas operaciones importantes (compras, ventas, servicios)?' },
  { question: '¿Qué canales de venta o plataformas usas actualmente?' },
];

const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  if (!token) return null;
  return { Authorization: `Bearer ${token}` };
};

const formatDateTime = (value) => {
  if (!value) return null;
  try {
    const date = new Date(value);
    return date.toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' });
  } catch (err) {
    return value;
  }
};

const Pill = ({ children, tone = 'indigo' }) => {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600 ring-indigo-200',
    green: 'bg-emerald-50 text-emerald-600 ring-emerald-200',
    slate: 'bg-slate-100 text-slate-700 ring-slate-200',
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${
        tones[tone] || tones.indigo
      }`}
    >
      {children}
    </span>
  );
};

const StepIndicator = ({ current }) => {
  const steps = [
    { id: STEPS.INTRO, label: 'Contexto base' },
    { id: STEPS.INTERVIEW, label: 'Entrevista' },
    { id: STEPS.REVIEW, label: 'Resumen final' },
  ];

  const activeIndex = steps.findIndex((step) => step.id === current);

  return (
    <div className="flex items-center justify-between gap-3">
      {steps.map((step, index) => (
        <div key={step.id} className="flex flex-1 items-center gap-3">
          <div
            className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold ${
              index <= activeIndex ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-600'
            }`}
          >
            {index + 1}
          </div>
          <div className="flex flex-col">
            <span
              className={`text-xs font-medium uppercase tracking-wide ${
                index <= activeIndex ? 'text-indigo-600' : 'text-slate-400'
              }`}
            >
              Paso {index + 1}
            </span>
            <span className="text-sm font-semibold text-slate-800">{step.label}</span>
          </div>
          {index < steps.length - 1 && (
            <div
              className={`h-px flex-1 ${
                index < activeIndex ? 'bg-indigo-200' : 'bg-slate-200'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
};

const compileNarrative = (seedText, questions, answers) => {
  const sections = [];
  const cleanedSeed = seedText.trim();
  if (cleanedSeed.length > 0) {
    sections.push(cleanedSeed);
  }

  questions.forEach((item, index) => {
    const answer = (answers[index] || '').trim();
    if (!answer) return;
    const cleanQuestion = item.question.replace(/\?$/, '');
    sections.push(`${cleanQuestion}: ${answer}`);
  });

  if (sections.length === 0) {
    return '';
  }

  return sections.join('\n\n');
};

const ContextWizard = () => {
  const [step, setStep] = useState(STEPS.INTRO);
  const [seedText, setSeedText] = useState('');
  const [contextStatus, setContextStatus] = useState(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [tokenMissing, setTokenMissing] = useState(false);
  const [error, setError] = useState(null);

  const [questions, setQuestions] = useState([]);
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [questionsError, setQuestionsError] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState({});

  const [submissionMode, setSubmissionMode] = useState('text');
  const [audioFile, setAudioFile] = useState(null);
  const [finalText, setFinalText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
    const [result, setResult] = useState(null);
    const [isUpdating, setIsUpdating] = useState(false);

    useEffect(() => {
        const loadStatus = async () => {
            const headers = getAuthHeaders();
            if (!headers) {
                setTokenMissing(true);
        setStatusLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_ROOT}/companies/context/status`, { headers });
        if (!response.ok) {
          throw new Error(`Error ${response.status}`);
        }
        const data = await response.json();
        setContextStatus(data);
      } catch (err) {
        console.error('Failed to load context status', err);
        setError('No fue posible obtener el resumen actual. Intenta nuevamente más tarde.');
      } finally {
        setStatusLoading(false);
      }
    };

        loadStatus();
    }, []);

    useEffect(() => {
        if (!statusLoading && !contextStatus?.summary) {
            setIsUpdating(true);
        }
    }, [statusLoading, contextStatus?.summary]);

    const beginUpdate = () => {
        setResult(null);
        setIsUpdating(true);
        setStep(STEPS.INTRO);
        setSeedText('');
    };

    const handleStartInterview = async () => {
        if (!isUpdating) {
            setIsUpdating(true);
        }
        setQuestionsError(null);
        setQuestionsLoading(true);
        setQuestions([]);
        setAnswers({});
        setQuestionIndex(0);

    const headers = getAuthHeaders();
    if (!headers) {
      setTokenMissing(true);
      setQuestionsLoading(false);
      return;
    }

    const seedCandidate = seedText.trim();
    const baseContext =
      seedCandidate.length >= 10
        ? seedCandidate
        : contextStatus?.summary || 'Necesito preguntas para perfilar una empresa nueva.';

    try {
      const response = await fetch(`${API_ROOT}/companies/context/questions`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          context: baseContext,
          count: 5,
        }),
      });

      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }

      const payload = await response.json();
      const parsedQuestions = Array.isArray(payload.questions) && payload.questions.length > 0
        ? payload.questions
        : DEFAULT_QUESTIONS;

      setQuestions(parsedQuestions);
      setStep(STEPS.INTERVIEW);
    } catch (err) {
      console.warn('Falling back to default questions', err);
      setQuestions(DEFAULT_QUESTIONS);
      setQuestionsError('No se pudieron generar preguntas dinámicas. Usaremos el guion estándar.');
      setStep(STEPS.INTERVIEW);
    } finally {
      setQuestionsLoading(false);
    }
  };

  const handleAnswerChange = (index, value) => {
    setAnswers((prev) => ({ ...prev, [index]: value }));
  };

  const handleNextQuestion = () => {
    if (questionIndex === questions.length - 1) {
      const narrative = compileNarrative(seedText, questions, answers);
      setFinalText(
        narrative.length > 0
          ? narrative
          : contextStatus?.summary || 'Describe aquí cómo opera tu empresa…'
      );
      setStep(STEPS.REVIEW);
      return;
    }
    setQuestionIndex((prev) => prev + 1);
  };

  const handlePreviousQuestion = () => {
    if (questionIndex === 0) {
      setStep(STEPS.INTRO);
      return;
    }
    setQuestionIndex((prev) => prev - 1);
  };

  const handleSkipQuestion = () => {
    setAnswers((prev) => ({ ...prev, [questionIndex]: '' }));
    handleNextQuestion();
  };

  const onManualReview = () => {
    const narrative = compileNarrative(seedText, questions, answers);
    const base = narrative || contextStatus?.summary || seedText || '';
    setFinalText(base);
    setStep(STEPS.REVIEW);
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    setAudioFile(file || null);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);

    const headers = getAuthHeaders();
    if (!headers) {
      setTokenMissing(true);
      return;
    }

    const cleaned = (finalText || '').trim();
    if (cleaned.length < 10) {
      setError('El resumen final debe tener al menos 10 caracteres.');
      return;
    }

    if (submissionMode === 'audio' && !audioFile) {
      setError('Adjunta una nota de voz o cambia a modo texto.');
      return;
    }

    setIsSubmitting(true);
    setResult(null);

    try {
      let response;
      if (submissionMode === 'audio') {
        const formData = new FormData();
        formData.append('input_type', 'audio');
        formData.append('content', cleaned);
        formData.append('file', audioFile);
        response = await fetch(`${API_ROOT}/companies/contextual_profile`, {
          method: 'POST',
          headers,
          body: formData,
        });
      } else {
        response = await fetch(`${API_ROOT}/companies/contextual_profile`, {
          method: 'POST',
          headers: {
            ...headers,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            input_type: 'text',
            content: cleaned,
          }),
        });
      }

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const detail = payload?.detail || response.statusText;
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }

      const payload = await response.json();
      setResult(payload);
      setSeedText('');
      setAudioFile(null);
      setAnswers({});
      setQuestions([]);
      setQuestionIndex(0);
      setSubmissionMode('text');
      setStep(STEPS.INTRO);
      setIsUpdating(false);

      setContextStatus((prev) => ({
        ...prev,
        summary: payload.summary,
        last_context_update: payload.last_refresh,
        topics: payload.topics,
      }));
    } catch (err) {
      console.error('Context submission failed', err);
      setError(err.message || 'No fue posible guardar el contexto de la empresa.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const currentQuestion = questions[questionIndex];
  const currentAnswer = answers[questionIndex] || '';
  const lastUpdateLabel = formatDateTime(contextStatus?.last_context_update);

  const reviewPreview = useMemo(() => {
    if (finalText.trim().length > 0) {
      return finalText.split('\n').slice(0, 2).join(' ');
    }
    return '';
  }, [finalText]);

  if (tokenMissing) {
    return (
      <div className="bg-white rounded-2xl shadow p-6 space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Contexto Operativo</h1>
        <p className="text-slate-600">
          Inicia sesión para capturar el contexto de tu empresa y personalizar la IA.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <header className="bg-white shadow rounded-2xl p-6 space-y-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-slate-900">
            🧠 Contexto Operativo de la Empresa
          </h1>
          <p className="text-sm text-slate-600">
            Responde una mini entrevista para que la IA entienda tu modelo de negocio, clientes,
            proveedores y canales. Con eso personalizamos la categorización de gastos y las
            recomendaciones contables.
          </p>
        </div>
        {isUpdating && <StepIndicator current={step} />}
        {statusLoading ? (
          <span className="text-xs text-slate-500 animate-pulse">Cargando contexto previo…</span>
        ) : (
          contextStatus?.last_context_update && (
            <span className="text-xs text-slate-500">
              Última actualización: {formatDateTime(contextStatus.last_context_update)}
            </span>
          )
        )}
      </header>

      {contextStatus?.summary && (
        <section className="bg-white rounded-2xl border border-slate-200 p-6 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Resumen actual</h2>
            <Pill>IA Context Memory</Pill>
          </div>
          <p className="text-slate-700 leading-relaxed">{contextStatus.summary}</p>
          {contextStatus.topics?.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {contextStatus.topics.map((topic) => (
                <Pill key={topic}>{topic}</Pill>
              ))}
            </div>
          )}
        </section>
      )}

      {!statusLoading && contextStatus?.summary && !isUpdating && (
        <section className="bg-white rounded-2xl border border-indigo-100 px-6 py-5 shadow-sm flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-indigo-900 font-medium">
              {lastUpdateLabel
                ? `Contexto actualizado el ${lastUpdateLabel}.`
                : 'Contexto listo para personalizar la IA.'}
            </p>
            <p className="text-xs text-indigo-700">
              Puedes actualizar la entrevista cuando quieras para mantener la IA alineada a los cambios del negocio.
            </p>
          </div>
          <button
            type="button"
            onClick={beginUpdate}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white shadow transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            Actualizar contexto
            <span aria-hidden="true">→</span>
          </button>
        </section>
      )}

      {isUpdating && step === STEPS.INTRO && (
        <section className="bg-white rounded-2xl shadow p-6 space-y-6">
          <div className="space-y-3">
            <h2 className="text-xl font-semibold text-slate-900">
              Cuéntanos brevemente sobre tu operación
            </h2>
            <p className="text-sm text-slate-600">
              Usa este espacio para dar contexto base. Esto ayuda a la IA a generar preguntas más
              relevantes. Después podrás grabar/adjuntar una nota de voz o complementar con el
              cuestionario.
            </p>
            <textarea
              className="w-full min-h-[160px] rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 shadow-inner focus:border-indigo-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-200"
              placeholder="Ej: Vendemos soluciones SaaS para restaurantes, cobramos suscripción mensual y damos soporte con un equipo de 5 personas en la CDMX..."
              value={seedText}
              onChange={(event) => setSeedText(event.target.value)}
            />
            <p className="text-xs text-slate-500">
              Incluye qué ofreces, a quién le vendes, cómo cobras y con quién operas. Con eso la IA
              entenderá mejor tu negocio.
            </p>
          </div>
          {questionsError && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {questionsError}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleStartInterview}
              disabled={questionsLoading}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white shadow transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:cursor-not-allowed disabled:bg-indigo-300"
            >
              {questionsLoading ? (
                <>
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Generando preguntas…
                </>
              ) : (
                <>
                  <span>Iniciar entrevista IA</span>
                  <span aria-hidden="true">→</span>
                </>
              )}
            </button>
            <button
              type="button"
              onClick={onManualReview}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-5 py-3 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
            >
              Saltar a resumen manual
            </button>
          </div>
        </section>
      )}

      {isUpdating && step === STEPS.INTERVIEW && (
        <section className="bg-white rounded-2xl shadow p-6 space-y-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-slate-900">Entrevista guiada</h2>
              <p className="text-sm text-slate-600">
                Responde con libertad. Puedes escribir bullets, narrar procesos o pegar notas que ya
                tengas.
              </p>
            </div>
            <Pill tone="slate">
              Pregunta {questionIndex + 1} de {questions.length || 1}
            </Pill>
          </div>
          <div className="space-y-4">
            <div className="rounded-2xl border border-indigo-100 bg-indigo-50 px-4 py-3 text-sm text-indigo-900 shadow-inner">
              {currentQuestion?.question || 'Cuéntanos más sobre tu empresa.'}
            </div>
            <textarea
              className="w-full min-h-[160px] rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-inner focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              placeholder="Escribe la respuesta aquí…"
              value={currentAnswer}
              onChange={(event) => handleAnswerChange(questionIndex, event.target.value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handlePreviousQuestion}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            >
              ← Anterior
            </button>
            <button
              type="button"
              onClick={handleSkipQuestion}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
            >
              Saltar pregunta
            </button>
            <button
              type="button"
              onClick={handleNextQuestion}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white shadow transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300"
            >
              {questionIndex === questions.length - 1 ? 'Ir a resumen' : 'Siguiente →'}
            </button>
          </div>
        </section>
      )}

      {isUpdating && step === STEPS.REVIEW && (
        <section className="bg-white rounded-2xl shadow p-6 space-y-6">
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-slate-900">Revisión final</h2>
            <p className="text-sm text-slate-600">
              Ajusta el resumen si lo necesitas. Al guardar, la IA actualizará la memoria de contexto,
              giro, canales y clientes clave.
            </p>
            {reviewPreview && (
              <Pill tone="green">Vista previa: {reviewPreview.substring(0, 80)}…</Pill>
            )}
          </div>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-3">
              <label className="block text-sm font-medium text-slate-700">
                Resumen consolidado
              </label>
              <textarea
                className="w-full min-h-[220px] rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-inner focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                value={finalText}
                onChange={(event) => setFinalText(event.target.value)}
              />
              <p className="text-xs text-slate-500">
                Tip: agrega si tus costos son servicios o mercancías, cómo facturas y si usas personal
                interno o proveedores externos.
              </p>
            </div>

            <div className="space-y-3">
              <span className="text-sm font-medium text-slate-700">Modo de envío</span>
              <div className="inline-flex rounded-full border border-slate-200 p-1 bg-slate-50">
                <button
                  type="button"
                  onClick={() => setSubmissionMode('text')}
                  className={`px-4 py-1 text-sm rounded-full transition ${
                    submissionMode === 'text'
                      ? 'bg-white shadow text-slate-900'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  Texto
                </button>
                <button
                  type="button"
                  onClick={() => setSubmissionMode('audio')}
                  className={`px-4 py-1 text-sm rounded-full transition ${
                    submissionMode === 'audio'
                      ? 'bg-white shadow text-slate-900'
                      : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  Texto + audio
                </button>
              </div>
            </div>

            {submissionMode === 'audio' && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-700">
                  Adjunta una nota de voz (MP3, M4A o WAV)
                </label>
                <input
                  type="file"
                  accept="audio/*"
                  onChange={handleFileChange}
                  className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-full file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-indigo-700 hover:file:bg-indigo-100"
                />
                <p className="text-xs text-slate-500">
                  Transcribiremos la nota y la combinaremos con el resumen para mejorar el contexto.
                </p>
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
                {error}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setStep(STEPS.INTERVIEW)}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
              >
                ← Volver a entrevistas
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium text-white shadow transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:cursor-not-allowed disabled:bg-indigo-300"
              >
                {isSubmitting ? (
                  <>
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    Guardando…
                  </>
                ) : (
                  <>
                    <span>Guardar contexto</span>
                    <span aria-hidden="true">→</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </section>
      )}

      {result && (
        <section className="bg-white rounded-2xl border border-green-200 p-6 space-y-3">
          <header className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-emerald-700">Contexto actualizado</h2>
            <Pill tone="green">{result.model_name || 'context-analyzer'}</Pill>
          </header>
          <p className="text-sm text-slate-600">
            Confianza del modelo:{' '}
            <span className="font-semibold text-slate-800">
              {(result.confidence_score * 100).toFixed(1)}%
            </span>
          </p>
          {result.summary && (
            <p className="text-slate-700 leading-relaxed">{result.summary}</p>
          )}
          {result.topics?.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2">
              {result.topics.map((topic) => (
                <Pill key={topic}>{topic}</Pill>
              ))}
            </div>
          )}
          <dl className="grid grid-cols-1 gap-4 pt-4 text-sm text-slate-600 sm:grid-cols-2">
            {result.giro && (
              <div>
                <dt className="font-medium text-slate-900">Giro</dt>
                <dd>{result.giro}</dd>
              </div>
            )}
            {result.modelo_negocio && (
              <div>
                <dt className="font-medium text-slate-900">Modelo de negocio</dt>
                <dd>{result.modelo_negocio}</dd>
              </div>
            )}
            {result.clientes_clave?.length > 0 && (
              <div className="sm:col-span-2">
                <dt className="font-medium text-slate-900">Clientes clave</dt>
                <dd className="flex flex-wrap gap-2 pt-1">
                  {result.clientes_clave.map((item) => (
                    <Pill key={item}>{item}</Pill>
                  ))}
                </dd>
              </div>
            )}
            {result.proveedores_clave?.length > 0 && (
              <div className="sm:col-span-2">
                <dt className="font-medium text-slate-900">Proveedores clave</dt>
                <dd className="flex flex-wrap gap-2 pt-1">
                  {result.proveedores_clave.map((item) => (
                    <Pill key={item}>{item}</Pill>
                  ))}
                </dd>
              </div>
            )}
            {result.canales_venta?.length > 0 && (
              <div className="sm:col-span-2">
                <dt className="font-medium text-slate-900">Canales de venta</dt>
                <dd className="flex flex-wrap gap-2 pt-1">
                  {result.canales_venta.map((item) => (
                    <Pill key={item}>{item}</Pill>
                  ))}
                </dd>
              </div>
            )}
            {result.frecuencia_operacion && (
              <div>
                <dt className="font-medium text-slate-900">Frecuencia operativa</dt>
                <dd>{result.frecuencia_operacion}</dd>
              </div>
            )}
          </dl>
        </section>
      )}
    </div>
  );
};

const rootElement = document.getElementById('context-wizard-root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<ContextWizard />);
}
