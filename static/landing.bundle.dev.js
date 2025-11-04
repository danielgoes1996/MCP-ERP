"use strict";

function _regenerator() { /*! regenerator-runtime -- Copyright (c) 2014-present, Facebook, Inc. -- license (MIT): https://github.com/babel/babel/blob/main/packages/babel-helpers/LICENSE */ var e, t, r = "function" == typeof Symbol ? Symbol : {}, n = r.iterator || "@@iterator", o = r.toStringTag || "@@toStringTag"; function i(r, n, o, i) { var c = n && n.prototype instanceof Generator ? n : Generator, u = Object.create(c.prototype); return _regeneratorDefine2(u, "_invoke", function (r, n, o) { var i, c, u, f = 0, p = o || [], y = !1, G = { p: 0, n: 0, v: e, a: d, f: d.bind(e, 4), d: function d(t, r) { return i = t, c = 0, u = e, G.n = r, a; } }; function d(r, n) { for (c = r, u = n, t = 0; !y && f && !o && t < p.length; t++) { var o, i = p[t], d = G.p, l = i[2]; r > 3 ? (o = l === n) && (u = i[(c = i[4]) ? 5 : (c = 3, 3)], i[4] = i[5] = e) : i[0] <= d && ((o = r < 2 && d < i[1]) ? (c = 0, G.v = n, G.n = i[1]) : d < l && (o = r < 3 || i[0] > n || n > l) && (i[4] = r, i[5] = n, G.n = l, c = 0)); } if (o || r > 1) return a; throw y = !0, n; } return function (o, p, l) { if (f > 1) throw TypeError("Generator is already running"); for (y && 1 === p && d(p, l), c = p, u = l; (t = c < 2 ? e : u) || !y;) { i || (c ? c < 3 ? (c > 1 && (G.n = -1), d(c, u)) : G.n = u : G.v = u); try { if (f = 2, i) { if (c || (o = "next"), t = i[o]) { if (!(t = t.call(i, u))) throw TypeError("iterator result is not an object"); if (!t.done) return t; u = t.value, c < 2 && (c = 0); } else 1 === c && (t = i["return"]) && t.call(i), c < 2 && (u = TypeError("The iterator does not provide a '" + o + "' method"), c = 1); i = e; } else if ((t = (y = G.n < 0) ? u : r.call(n, G)) !== a) break; } catch (t) { i = e, c = 1, u = t; } finally { f = 1; } } return { value: t, done: y }; }; }(r, o, i), !0), u; } var a = {}; function Generator() {} function GeneratorFunction() {} function GeneratorFunctionPrototype() {} t = Object.getPrototypeOf; var c = [][n] ? t(t([][n]())) : (_regeneratorDefine2(t = {}, n, function () { return this; }), t), u = GeneratorFunctionPrototype.prototype = Generator.prototype = Object.create(c); function f(e) { return Object.setPrototypeOf ? Object.setPrototypeOf(e, GeneratorFunctionPrototype) : (e.__proto__ = GeneratorFunctionPrototype, _regeneratorDefine2(e, o, "GeneratorFunction")), e.prototype = Object.create(u), e; } return GeneratorFunction.prototype = GeneratorFunctionPrototype, _regeneratorDefine2(u, "constructor", GeneratorFunctionPrototype), _regeneratorDefine2(GeneratorFunctionPrototype, "constructor", GeneratorFunction), GeneratorFunction.displayName = "GeneratorFunction", _regeneratorDefine2(GeneratorFunctionPrototype, o, "GeneratorFunction"), _regeneratorDefine2(u), _regeneratorDefine2(u, o, "Generator"), _regeneratorDefine2(u, n, function () { return this; }), _regeneratorDefine2(u, "toString", function () { return "[object Generator]"; }), (_regenerator = function _regenerator() { return { w: i, m: f }; })(); }
function _regeneratorDefine2(e, r, n, t) { var i = Object.defineProperty; try { i({}, "", {}); } catch (e) { i = 0; } _regeneratorDefine2 = function _regeneratorDefine(e, r, n, t) { function o(r, n) { _regeneratorDefine2(e, r, function (e) { return this._invoke(r, n, e); }); } r ? i ? i(e, r, { value: n, enumerable: !t, configurable: !t, writable: !t }) : e[r] = n : (o("next", 0), o("throw", 1), o("return", 2)); }, _regeneratorDefine2(e, r, n, t); }
function asyncGeneratorStep(n, t, e, r, o, a, c) { try { var i = n[a](c), u = i.value; } catch (n) { return void e(n); } i.done ? t(u) : Promise.resolve(u).then(r, o); }
function _asyncToGenerator(n) { return function () { var t = this, e = arguments; return new Promise(function (r, o) { var a = n.apply(t, e); function _next(n) { asyncGeneratorStep(a, r, o, _next, _throw, "next", n); } function _throw(n) { asyncGeneratorStep(a, r, o, _next, _throw, "throw", n); } _next(void 0); }); }; }
function _slicedToArray(r, e) { return _arrayWithHoles(r) || _iterableToArrayLimit(r, e) || _unsupportedIterableToArray(r, e) || _nonIterableRest(); }
function _nonIterableRest() { throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }
function _unsupportedIterableToArray(r, a) { if (r) { if ("string" == typeof r) return _arrayLikeToArray(r, a); var t = {}.toString.call(r).slice(8, -1); return "Object" === t && r.constructor && (t = r.constructor.name), "Map" === t || "Set" === t ? Array.from(r) : "Arguments" === t || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(t) ? _arrayLikeToArray(r, a) : void 0; } }
function _arrayLikeToArray(r, a) { (null == a || a > r.length) && (a = r.length); for (var e = 0, n = Array(a); e < a; e++) n[e] = r[e]; return n; }
function _iterableToArrayLimit(r, l) { var t = null == r ? null : "undefined" != typeof Symbol && r[Symbol.iterator] || r["@@iterator"]; if (null != t) { var e, n, i, u, a = [], f = !0, o = !1; try { if (i = (t = t.call(r)).next, 0 === l) { if (Object(t) !== t) return; f = !1; } else for (; !(f = (e = i.call(t)).done) && (a.push(e.value), a.length !== l); f = !0); } catch (r) { o = !0, n = r; } finally { try { if (!f && null != t["return"] && (u = t["return"](), Object(u) !== u)) return; } finally { if (o) throw n; } } return a; } }
function _arrayWithHoles(r) { if (Array.isArray(r)) return r; }
var _React = React,
  useMemo = _React.useMemo,
  useEffect = _React.useEffect,
  useState = _React.useState,
  useRef = _React.useRef;
var ContaFlowLanding = function ContaFlowLanding() {
  var _useState = useState(false),
    _useState2 = _slicedToArray(_useState, 2),
    particlesLoaded = _useState2[0],
    setParticlesLoaded = _useState2[1];
  useEffect(function () {
    var initParticles = /*#__PURE__*/function () {
      var _ref = _asyncToGenerator(/*#__PURE__*/_regenerator().m(function _callee() {
        var _t;
        return _regenerator().w(function (_context) {
          while (1) switch (_context.p = _context.n) {
            case 0:
              if (window.tsParticles) {
                _context.n = 1;
                break;
              }
              return _context.a(2);
            case 1:
              _context.p = 1;
              _context.n = 2;
              return window.tsParticles.load({
                id: "hero-particles",
                options: {
                  background: {
                    color: {
                      value: "transparent"
                    }
                  },
                  fpsLimit: 60,
                  interactivity: {
                    events: {
                      onHover: {
                        enable: true,
                        mode: "grab"
                      },
                      onClick: {
                        enable: true,
                        mode: "push"
                      },
                      resize: true
                    },
                    modes: {
                      grab: {
                        distance: 180,
                        links: {
                          opacity: 0.35
                        }
                      },
                      push: {
                        quantity: 2
                      }
                    }
                  },
                  particles: {
                    color: {
                      value: ["#B1F5D9", "#88E8B5", "#5ED694"]
                    },
                    links: {
                      color: "#78E0AE",
                      distance: 150,
                      enable: true,
                      opacity: 0.3,
                      width: 1
                    },
                    move: {
                      enable: true,
                      speed: 0.6,
                      random: true,
                      direction: "none",
                      outModes: {
                        "default": "bounce"
                      }
                    },
                    number: {
                      value: 110,
                      density: {
                        enable: true,
                        area: 900
                      }
                    },
                    opacity: {
                      value: 0.8
                    },
                    shape: {
                      type: "circle"
                    },
                    size: {
                      value: {
                        min: 1.5,
                        max: 4.5
                      }
                    }
                  },
                  detectRetina: true
                }
              });
            case 2:
              setParticlesLoaded(true);
              _context.n = 4;
              break;
            case 3:
              _context.p = 3;
              _t = _context.v;
              console.warn("No se pudieron inicializar las partículas:", _t);
            case 4:
              return _context.a(2);
          }
        }, _callee, null, [[1, 3]]);
      }));
      return function initParticles() {
        return _ref.apply(this, arguments);
      };
    }();
    initParticles();
  }, []);
  useEffect(function () {
    var styleId = "contaflow-landing-animations";
    if (document.getElementById(styleId)) {
      return;
    }
    var style = document.createElement("style");
    style.id = styleId;
    style.textContent = "\n            @keyframes auroraShift {\n                0% { transform: translate3d(-4%, -2%, 0); background-position: 0% 50%; }\n                50% { transform: translate3d(0%, 4%, 0); background-position: 50% 30%; }\n                100% { transform: translate3d(6%, -3%, 0); background-position: 100% 70%; }\n            }\n            @keyframes ctaPulse {\n                0% { transform: scale(0.95); opacity: 0.45; }\n                50% { transform: scale(1.03); opacity: 0.7; }\n                100% { transform: scale(1.08); opacity: 0.4; }\n            }\n            .hero-aurora {\n                position: relative;\n                isolation: isolate;\n            }\n            .hero-aurora::before {\n                content: \"\";\n                position: absolute;\n                inset: -160px -220px;\n                background: radial-gradient(circle at 20% 20%, rgba(132, 216, 168, 0.28), transparent 55%),\n                            radial-gradient(circle at 80% 30%, rgba(45, 109, 170, 0.24), transparent 60%),\n                            linear-gradient(120deg, rgba(30, 94, 156, 0.24), rgba(96, 185, 123, 0.22));\n                background-size: 180% 180%;\n                filter: blur(70px);\n                opacity: 0.35;\n                border-radius: 36px;\n                animation: auroraShift 16s ease-in-out infinite alternate;\n                z-index: -1;\n            }\n            .reveal-on-scroll {\n                opacity: 0;\n                transform: translateY(28px);\n                transition: opacity 0.8s cubic-bezier(0.2, 0.6, 0.3, 1), transform 0.8s cubic-bezier(0.2, 0.6, 0.3, 1);\n            }\n            .reveal-on-scroll.is-visible {\n                opacity: 1;\n                transform: translateY(0);\n            }\n            .pill-button {\n                position: relative;\n                overflow: hidden;\n            }\n            .pill-button::after {\n                content: \"\";\n                position: absolute;\n                inset: 0;\n                transform: translateX(-120%);\n                transition: transform 0.6s ease;\n            }\n            .pill-button--solid::after {\n                background: linear-gradient(120deg, rgba(255, 255, 255, 0) 0%, rgba(255, 255, 255, 0.4) 45%, rgba(255, 255, 255, 0) 100%);\n            }\n            .pill-button--ghost::after {\n                background: linear-gradient(120deg, rgba(45, 109, 170, 0) 0%, rgba(45, 109, 170, 0.14) 45%, rgba(45, 109, 170, 0) 100%);\n            }\n            .pill-button:hover::after {\n                transform: translateX(120%);\n            }\n            [data-parallax=\"tilt\"] {\n                perspective: 1200px;\n            }\n            [data-parallax=\"tilt\"] img {\n                transition: transform 0.4s ease, opacity 0.4s ease;\n                will-change: transform;\n            }\n            [data-parallax=\"tilt\"].is-tilting img {\n                transform: rotateX(var(--tilt-x, 0deg)) rotateY(var(--tilt-y, 0deg)) scale(1.03);\n            }\n            .timeline-progress-track {\n                pointer-events: none;\n                position: absolute;\n                left: 50%;\n                top: 140px;\n                bottom: 140px;\n                width: 2px;\n                transform: translateX(-50%);\n                background: linear-gradient(to bottom, rgba(45, 109, 170, 0.18), rgba(96, 185, 123, 0.18));\n                overflow: hidden;\n                border-radius: 999px;\n                opacity: 0;\n                transition: opacity 0.6s ease;\n            }\n            .timeline-progress-track::after {\n                content: \"\";\n                position: absolute;\n                left: 0;\n                right: 0;\n                bottom: 0;\n                height: 0%;\n                background: linear-gradient(to bottom, rgba(45, 109, 170, 0.65), rgba(96, 185, 123, 0.55));\n                transition: height 1s ease;\n            }\n            .timeline-progress-track.is-visible {\n                opacity: 1;\n            }\n            .timeline-progress-track.is-visible::after {\n                height: 100%;\n            }\n            .cta-card::before {\n                content: \"\";\n                position: absolute;\n                inset: -40px;\n                border-radius: inherit;\n                background: radial-gradient(circle at 30% 30%, rgba(96, 185, 123, 0.25), transparent 55%),\n                            radial-gradient(circle at 70% 70%, rgba(45, 109, 170, 0.24), transparent 60%);\n                filter: blur(40px);\n                opacity: 0.6;\n                animation: ctaPulse 10s ease-in-out infinite alternate;\n                z-index: -1;\n            }\n            @media (prefers-reduced-motion: reduce) {\n                .hero-aurora::before,\n                .pill-button::after,\n                [data-parallax=\"tilt\"] img,\n                .timeline-progress-track::after,\n                .cta-card::before {\n                    animation: none !important;\n                    transition: none !important;\n                }\n                .reveal-on-scroll {\n                    opacity: 1 !important;\n                    transform: none !important;\n                }\n            }\n        ";
    document.head.appendChild(style);
  }, []);
  useEffect(function () {
    var revealElements = Array.from(document.querySelectorAll("[data-animate='reveal']"));
    if (revealElements.length === 0) {
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.15,
      rootMargin: "0px 0px -10% 0px"
    });
    revealElements.forEach(function (element) {
      return observer.observe(element);
    });
    return function () {
      return observer.disconnect();
    };
  }, []);
  useEffect(function () {
    var parallaxCards = Array.from(document.querySelectorAll("[data-parallax='tilt']"));
    if (!parallaxCards.length) {
      return;
    }
    var maxTilt = 8;
    var onMouseEnter = function onMouseEnter(event) {
      event.currentTarget.classList.add("is-tilting");
    };
    var onMouseLeave = function onMouseLeave(event) {
      var target = event.currentTarget;
      target.classList.remove("is-tilting");
      target.style.removeProperty("--tilt-x");
      target.style.removeProperty("--tilt-y");
    };
    var onMouseMove = function onMouseMove(event) {
      var target = event.currentTarget;
      var rect = target.getBoundingClientRect();
      var offsetX = (event.clientX - rect.left) / rect.width * 2 - 1;
      var offsetY = (event.clientY - rect.top) / rect.height * 2 - 1;
      target.style.setProperty("--tilt-x", "".concat((-offsetY * maxTilt).toFixed(2), "deg"));
      target.style.setProperty("--tilt-y", "".concat((offsetX * maxTilt).toFixed(2), "deg"));
    };
    parallaxCards.forEach(function (card) {
      card.addEventListener("mouseenter", onMouseEnter);
      card.addEventListener("mouseleave", onMouseLeave);
      card.addEventListener("mousemove", onMouseMove);
    });
    return function () {
      parallaxCards.forEach(function (card) {
        card.removeEventListener("mouseenter", onMouseEnter);
        card.removeEventListener("mouseleave", onMouseLeave);
        card.removeEventListener("mousemove", onMouseMove);
      });
    };
  }, []);
  useEffect(function () {
    var timelineSection = document.getElementById("timeline");
    var track = document.querySelector(".timeline-progress-track");
    if (!timelineSection || !track) {
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          track.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.25
    });
    observer.observe(timelineSection);
    return function () {
      return observer.disconnect();
    };
  }, []);
  var aiLayers = useMemo(function () {
    return [{
      icon: "🧠",
      title: "Inteligencia Cognitiva",
      desc: "Comprende el contexto de tu empresa desde el primer día: catálogo de cuentas, facturas y estados de cuenta. La migración es instantánea y, conforme confirmas operaciones, el sistema aprende de tu forma de trabajar, haciendo tu contabilidad más inteligente y eficiente."
    }, {
      icon: "⚡",
      title: "Inteligencia de Procesamiento",
      desc: "Reconoce la naturaleza de cada operación y clasifica automáticamente gastos, ingresos, traspasos y facturas, mapeándolos al catálogo de cuentas del SAT y a tus cuentas internas. Genera asientos y pólizas en las cuentas correctas y puede convertir tickets en CFDI cuando llegan por WhatsApp."
    }, {
      icon: "🤖",
      title: "Inteligencia Operativa",
      desc: "Ejecuta conciliaciones bancarias, generación de pólizas y reportes financieros en segundos. Cada movimiento queda vinculado a su factura y a su operación bancaria, con trazabilidad explicable para que tu equipo solo valide y analice."
    }];
  }, []);
  var modules = useMemo(function () {
    return [{
      title: "Captura inteligente omnicanal",
      description: "OCR fiscal, clasificación enriquecida y detección antifraude. Cada documento se convierte en gasto listo para auditoría.",
      bullets: ["Emails, WhatsApp y app móvil conectados a un mismo flujo.", "Motor antifraude: UUID vencidos y duplicados marcados al instante.", "Asignación automática de proyectos, centros de costo y responsables."],
      screenshot: "/static/img/landing-gasto.png"
    }, {
      title: "Conciliación bancaria asistida",
      description: "Motor híbrido ML + reglas que aprende con cada aprobación. Sugiere coincidencias y explica la decisión.",
      bullets: ["Detección de split payments y transferencias atípicas.", "Panel de pendientes por banco y prioridad.", "Aprendizaje continuo con feedback humano."],
      screenshot: "/static/img/landing-bancos.png"
    }, {
      title: "Contabilidad y reporting autónomos",
      description: "Genera pólizas, libros y KPIs gerenciales sin hojas de cálculo. Contabilidad viva en tiempo real.",
      bullets: ["Pólizas con explicación en lenguaje natural.", "Dashboards fiscales y administrativos siempre actualizados.", "Historial auditable de cada decisión del copiloto."],
      screenshot: "/static/img/landing-contexto.png"
    }];
  }, []);
  var flows = useMemo(function () {
    return [{
      title: "Captura y digitalización en segundos",
      kicker: "Tickets, facturas y transferencias limpias en un mismo lugar.",
      description: "Reenvía tus correos, sube fotos o deja que tu equipo reporte desde la app móvil. El motor cognitivo detecta CFDI, categorías y deducibilidad sin intervención manual.",
      bullets: ["Reconocimiento de UUID con validación SAT.", "Clasificación enriquecida con catálogo SAT + políticas internas.", "Asignación automática de responsables y proyectos."],
      screenshot: "/static/img/landing-gasto.png"
    }, {
      title: "Conciliación bancaria sin fricción",
      kicker: "Cada movimiento encuentra su par contable, y te dice por qué.",
      description: "Integramos bancos, tarjetas corporativas y wallets. El copiloto sugiere coincidencias con explicación en lenguaje natural; tú decides en un clic.",
      bullets: ["Detección predictiva de pagos fraccionados.", "Panel de pendientes por banco con level of confidence.", "Feedback loop para mejorar con cada aprobación."],
      screenshot: "/static/img/landing-conciliacion.png"
    }, {
      title: "Contabilidad viva y 100% auditable",
      kicker: "Pólizas, libros y KPIs actualizados todos los días.",
      description: "Cuenta con un copiloto que genera pólizas y justifica cada asiento. Los reportes fiscales y tesorería se actualizan solos al cierre del día.",
      bullets: ["Explainable AI: razones de cada póliza en español claro.", "KPIs gerenciales listos para juntas de dirección.", "Historial de cambios y bitácora lista para auditoría."],
      screenshot: "/static/img/landing-contexto.png"
    }];
  }, []);
  var uiShowcase = useMemo(function () {
    return [{
      title: "Registro de gasto en segundos",
      caption: "Carga un ticket o CFDI y observa cómo el copiloto completa la información clave al instante.",
      image: "/static/img/landing-gasto.png"
    }, {
      title: "Conciliación bancaria con IA",
      caption: "Cada sugerencia llega con explicación en lenguaje natural y nivel de confianza.",
      image: "/static/img/landing-conciliacion.png"
    }, {
      title: "Panel de cuentas y terminales",
      caption: "Controla bancos, terminales y efectivo desde un mismo tablero operativo.",
      image: "/static/img/landing-bancos.png"
    }, {
      title: "Login seguro y multiempresa",
      caption: "Gestiona múltiples razones sociales con autenticación unificada y selección de tenant.",
      image: "/static/img/landing-login.png"
    }, {
      title: "Contexto vivo de la empresa",
      caption: "La entrevista inteligente alimenta recomendaciones y clasificaciones personalizadas.",
      image: "/static/img/landing-contexto.png"
    }];
  }, []);
  var timeline = useMemo(function () {
    return [{
      title: "Onboarding asistido",
      description: "Conectamos bancos, SAT y sistemas previos. Limpiamos catálogos y migramos históricos en horas, no semanas."
    }, {
      title: "Captura omnicanal",
      description: "Habilita email forwarding, WhatsApp y app móvil. Cada ticket o CFDI llega clasificado sin Excel."
    }, {
      title: "Conciliación continua",
      description: "Cada mañana el panel muestra qué movimientos se conciliaron solos y cuáles requieren tu revisión."
    }, {
      title: "Contabilidad autónoma",
      description: "Generamos pólizas, libros y KPIs. El equipo contable valida y aprueba; la IA documenta y explica."
    }];
  }, []);
  var StatBadge = function StatBadge(_ref2) {
    var label = _ref2.label,
      value = _ref2.value;
    var badgeRef = useRef(null);
    var parsedValue = useMemo(function () {
      var match = value.match(/^(\d+)(.*)$/);
      if (!match) {
        return {
          number: null,
          suffix: "",
          full: value
        };
      }
      return {
        number: Number(match[1]),
        suffix: match[2]
      };
    }, [value]);
    var _useState3 = useState(parsedValue.number !== null ? 0 : null),
      _useState4 = _slicedToArray(_useState3, 2),
      displayNumber = _useState4[0],
      setDisplayNumber = _useState4[1];
    useEffect(function () {
      if (parsedValue.number === null) {
        setDisplayNumber(null);
        return;
      }
      setDisplayNumber(0);
      var badge = badgeRef.current;
      if (!badge) {
        return;
      }
      var frame;
      var hasAnimated = false;
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !hasAnimated) {
            hasAnimated = true;
            var start = performance.now();
            var duration = 1600;
            var _animate = function animate(now) {
              var progress = Math.min((now - start) / duration, 1);
              var eased = 1 - Math.pow(1 - progress, 3);
              var currentValue = Math.round(parsedValue.number * eased);
              setDisplayNumber(currentValue);
              if (progress < 1) {
                frame = requestAnimationFrame(_animate);
              } else {
                setDisplayNumber(parsedValue.number);
              }
            };
            frame = requestAnimationFrame(_animate);
            observer.disconnect();
          }
        });
      }, {
        threshold: 0.6
      });
      observer.observe(badge);
      return function () {
        if (frame) {
          cancelAnimationFrame(frame);
        }
        observer.disconnect();
      };
    }, [parsedValue]);
    var renderValue = parsedValue.number === null || displayNumber === null ? parsedValue.full || value : "".concat(displayNumber.toLocaleString()).concat(parsedValue.suffix);
    return /*#__PURE__*/React.createElement("div", {
      ref: badgeRef,
      className: "rounded-2xl bg-white/95 backdrop-blur border border-[#D9E8F5] px-6 py-5 shadow-[0_18px_45px_rgba(17,68,110,0.08)] reveal-on-scroll",
      "data-animate": "reveal"
    }, /*#__PURE__*/React.createElement("p", {
      className: "text-xs uppercase tracking-widest text-[#2D6DAA] font-semibold mb-2"
    }, label), /*#__PURE__*/React.createElement("p", {
      className: "text-lg text-[#11446E] font-semibold"
    }, /*#__PURE__*/React.createElement("span", {
      className: "stat-count-value"
    }, renderValue)));
  };
  var PillButton = function PillButton(_ref3) {
    var children = _ref3.children,
      _ref3$variant = _ref3.variant,
      variant = _ref3$variant === void 0 ? "solid" : _ref3$variant,
      href = _ref3.href;
    var baseStyles = "pill-button rounded-full px-8 py-3 text-sm font-semibold transition-transform transform hover:-translate-y-0.5";
    var styles = variant === "ghost" ? "pill-button--ghost border border-[#D9E8F5] text-[#11446E] hover:bg-[#F2F9FF]" : "pill-button--solid bg-[#60B97B] hover:bg-[#4FA771] text-white shadow-[0_18px_40px_rgba(96,185,123,0.35)]";
    var Component = href ? "a" : "button";
    return /*#__PURE__*/React.createElement(Component, {
      href: href,
      className: "".concat(baseStyles, " ").concat(styles)
    }, children);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: "relative min-h-screen flex flex-col bg-gradient-to-b from-white via-white to-[#F1F8F5] text-[#11446E] font-sans overflow-hidden"
  }, /*#__PURE__*/React.createElement("div", {
    id: "hero-particles",
    className: "absolute inset-0 pointer-events-none"
  }), !particlesLoaded && /*#__PURE__*/React.createElement("div", {
    className: "absolute inset-0 pointer-events-none bg-gradient-to-b from-[#0F3656] via-[#11446E] to-transparent"
  }), /*#__PURE__*/React.createElement("header", {
    className: "relative z-20 bg-white/95 backdrop-blur-md border-b border-[#D9E8F5] shadow-[0_10px_40px_rgba(17,68,110,0.08)]"
  }, /*#__PURE__*/React.createElement("nav", {
    className: "max-w-6xl mx-auto flex items-center justify-between px-6 py-6 text-[#11446E]"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-3"
  }, /*#__PURE__*/React.createElement("img", {
    src: "/static/img/ContaFlow.png",
    alt: "ContaFlow Logo",
    width: 240,
    height: 96,
    className: "drop-shadow-[0_18px_40px_rgba(17,68,110,0.18)]"
  })), /*#__PURE__*/React.createElement("div", {
    className: "hidden md:flex items-center gap-6 text-sm text-[#2D6DAA]"
  }, /*#__PURE__*/React.createElement("a", {
    href: "#modules",
    className: "hover:text-[#11446E] transition-colors"
  }, "Producto"), /*#__PURE__*/React.createElement("a", {
    href: "#flows",
    className: "hover:text-[#11446E] transition-colors"
  }, "Flujos"), /*#__PURE__*/React.createElement("a", {
    href: "#timeline",
    className: "hover:text-[#11446E] transition-colors"
  }, "C\xF3mo funciona"), /*#__PURE__*/React.createElement("a", {
    href: "#cta",
    className: "hover:text-[#11446E] transition-colors"
  }, "Beta")), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-3"
  }, /*#__PURE__*/React.createElement(PillButton, {
    variant: "ghost",
    href: "/auth-login.html"
  }, "Iniciar sesi\xF3n"), /*#__PURE__*/React.createElement(PillButton, {
    href: "#cta"
  }, "Unirme a la beta")))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 py-24 px-6 bg-gradient-to-b from-[#0F3656] via-[#11446E] to-transparent text-white"
  }, /*#__PURE__*/React.createElement("div", {
    className: "pointer-events-none absolute inset-x-0 -top-32 h-[420px] bg-gradient-to-b from-white/15 via-white/5 to-transparent blur-3xl opacity-80"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative flex flex-col items-center text-center max-w-6xl mx-auto gap-12 hero-aurora"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex flex-col items-center gap-6 reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("div", {
    className: "inline-flex items-center gap-3 bg-white/95 border border-[#D9E8F5] px-5 py-2.5 rounded-full text-xs uppercase tracking-[0.32em] text-[#11446E] shadow-[0_18px_45px_rgba(17,68,110,0.25)]"
  }, "Contabilidad aut\xF3noma con IA explicable"), /*#__PURE__*/React.createElement("h1", {
    className: "text-5xl md:text-6xl lg:text-7xl font-black leading-tight text-white drop-shadow-[0_22px_45px_rgba(0,0,0,0.35)]"
  }, "Tu contabilidad, organizada desde el primer gasto."), /*#__PURE__*/React.createElement("p", {
    className: "text-lg md:text-xl text-[#E6F0FA] max-w-3xl"
  }, "Captura gastos e ingresos desde voz, texto o WhatsApp, vincula o genera las facturas correspondientes y conc\xEDlialas autom\xE1ticamente con tus bancos."), /*#__PURE__*/React.createElement("p", {
    className: "text-base text-[#DCE9F8] max-w-3xl"
  }, "Automatizamos la generaci\xF3n de p\xF3lizas y la conciliaci\xF3n contable para que t\xFA y tu equipo se enfoquen en verificar, analizar y confirmar, no en capturar. Una contabilidad precisa, eficiente y en tiempo real, sin procesos tediosos."), /*#__PURE__*/React.createElement("div", {
    className: "flex flex-col md:flex-row gap-4"
  }, /*#__PURE__*/React.createElement(PillButton, {
    href: "#beta"
  }, "\uD83C\uDF81 \xDAnete a la beta gratuita para contadores"))), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-1 sm:grid-cols-3 gap-6 w-full text-left reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement(StatBadge, {
    label: "Tiempo ahorrado",
    value: "82% menos horas de captura"
  }), /*#__PURE__*/React.createElement(StatBadge, {
    label: "Automatizaci\xF3n real",
    value: "91% de gastos conciliados solos"
  }), /*#__PURE__*/React.createElement(StatBadge, {
    label: "Visibilidad total",
    value: "KPIs y p\xF3lizas en tiempo real"
  })))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 bg-white py-24 px-8 overflow-hidden",
    id: "layers"
  }, /*#__PURE__*/React.createElement("div", {
    className: "pointer-events-none absolute inset-x-12 top-12 h-64 rounded-[48px] bg-gradient-to-r from-[#E8F6EE] via-white to-[#E6F1FD] blur-2xl opacity-80"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto text-center mb-16 reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-4xl font-bold mb-4 bg-gradient-to-r from-[#84D8A8] to-[#3C7FC0] text-transparent bg-clip-text"
  }, "Tres inteligencias que aprenden de tu negocio"), /*#__PURE__*/React.createElement("p", {
    className: "text-[#40566C] text-lg max-w-3xl mx-auto"
  }, "Combinamos modelos cognitivos, operativos y de decisi\xF3n para automatizar todo el ciclo contable. T\xFA eliges qu\xE9 aprueba la IA y qu\xE9 decides validar.")), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto grid sm:grid-cols-2 lg:grid-cols-3 gap-8 text-left"
  }, aiLayers.map(function (layer) {
    return /*#__PURE__*/React.createElement("div", {
      key: layer.title,
      className: "bg-white/95 backdrop-blur border border-[#D9E8F5] rounded-3xl p-8 shadow-[0_18px_45px_rgba(17,68,110,0.08)] hover:-translate-y-1 hover:shadow-[0_28px_60px_rgba(17,68,110,0.16)] transition-all reveal-on-scroll",
      "data-animate": "reveal"
    }, /*#__PURE__*/React.createElement("div", {
      className: "text-3xl mb-4"
    }, layer.icon), /*#__PURE__*/React.createElement("h3", {
      className: "text-2xl font-semibold mb-3 text-[#11446E]"
    }, layer.title), /*#__PURE__*/React.createElement("p", {
      className: "text-[#40566C] text-base leading-relaxed"
    }, layer.desc));
  }))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 py-24 px-8 bg-white overflow-hidden",
    id: "modules"
  }, /*#__PURE__*/React.createElement("div", {
    className: "pointer-events-none absolute -top-24 right-16 w-72 h-72 rounded-full bg-gradient-to-br from-[#E8F6EE] via-transparent to-[#E6F1FD] blur-3xl opacity-80"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto mb-16 text-center reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-4xl font-bold mb-4 bg-gradient-to-r from-[#84D8A8] to-[#3C7FC0] text-transparent bg-clip-text"
  }, "El Sistema operativo contable que evoluciona contigo"), /*#__PURE__*/React.createElement("p", {
    className: "text-[#40566C] text-lg max-w-3xl mx-auto"
  }, "Nuestra tecnolog\xEDa combina tres niveles de inteligencia que trabajan en conjunto para automatizar todo el ciclo contable. T\xFA eliges qu\xE9 aprueba la IA y qu\xE9 prefieres validar.")), /*#__PURE__*/React.createElement("div", {
    className: "max-w-6xl mx-auto space-y-16"
  }, modules.map(function (module, index) {
    return /*#__PURE__*/React.createElement("div", {
      key: module.title,
      className: "grid md:grid-cols-2 gap-12 items-center reveal-on-scroll ".concat(index % 2 !== 0 ? "md:flex-row-reverse" : ""),
      "data-animate": "reveal"
    }, /*#__PURE__*/React.createElement("div", {
      className: "space-y-5"
    }, /*#__PURE__*/React.createElement("span", {
      className: "inline-flex items-center gap-2 text-xs uppercase tracking-widest text-[#2D6DAA]"
    }, /*#__PURE__*/React.createElement("span", {
      className: "text-lg"
    }, "\uD83D\uDCA1"), "M\xF3dulo"), /*#__PURE__*/React.createElement("h3", {
      className: "text-3xl font-semibold text-[#11446E]"
    }, module.title), /*#__PURE__*/React.createElement("p", {
      className: "text-[#40566C] leading-relaxed"
    }, module.description), /*#__PURE__*/React.createElement("ul", {
      className: "space-y-3 text-[#46617A]"
    }, module.bullets.map(function (item) {
      return /*#__PURE__*/React.createElement("li", {
        key: item,
        className: "flex items-start gap-3"
      }, /*#__PURE__*/React.createElement("span", {
        className: "text-[#2D6DAA] mt-0.5"
      }, "\u25CF"), /*#__PURE__*/React.createElement("span", null, item));
    }))), /*#__PURE__*/React.createElement("div", {
      className: "relative rounded-3xl overflow-hidden border border-[#D9E8F5] bg-white shadow-[0_22px_60px_rgba(17,68,110,0.12)] parallax-card",
      "data-parallax": "tilt"
    }, /*#__PURE__*/React.createElement("img", {
      src: module.screenshot,
      alt: "Vista previa del m\xF3dulo ".concat(module.title),
      className: "w-full h-full object-cover"
    }), /*#__PURE__*/React.createElement("div", {
      className: "pointer-events-none absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-white via-white/60 to-transparent"
    }), /*#__PURE__*/React.createElement("div", {
      className: "pointer-events-none absolute top-4 left-4 inline-flex items-center gap-2 rounded-full bg-white/90 px-4 py-2 text-xs font-semibold text-[#11446E] shadow-[0_12px_30px_rgba(17,68,110,0.12)]"
    }, /*#__PURE__*/React.createElement("span", {
      className: "h-2.5 w-2.5 rounded-full bg-[#60B97B]"
    }), "Vista previa del m\xF3dulo")));
  }))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 py-28 px-8 bg-white overflow-hidden",
    id: "flows"
  }, /*#__PURE__*/React.createElement("div", {
    className: "pointer-events-none absolute inset-x-10 top-0 h-72 bg-gradient-to-b from-[#E6F1FD] via-white to-transparent blur-2xl opacity-90"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto text-center mb-16 reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-4xl font-bold mb-4 bg-gradient-to-r from-[#84D8A8] to-[#3C7FC0] text-transparent bg-clip-text"
  }, "Flujos inteligentes que documentan cada decisi\xF3n"), /*#__PURE__*/React.createElement("p", {
    className: "text-[#40566C] text-lg max-w-3xl mx-auto"
  }, "La IA toma la carga operativa y deja un rastro explicable para contadores, CFOs y auditor\xEDas.")), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto space-y-16"
  }, flows.map(function (flow) {
    return /*#__PURE__*/React.createElement("div", {
      key: flow.title,
      className: "bg-gradient-to-br from-white via-[#F6FCFF] to-[#EBF5FF] border border-[#D9E8F5] rounded-3xl p-8 md:p-12 shadow-[0_24px_60px_rgba(17,68,110,0.12)] grid md:grid-cols-2 gap-10 items-center reveal-on-scroll",
      "data-animate": "reveal"
    }, /*#__PURE__*/React.createElement("div", {
      className: "space-y-4 text-left"
    }, /*#__PURE__*/React.createElement("span", {
      className: "text-xs uppercase tracking-widest text-[#2D6DAA]"
    }, flow.kicker), /*#__PURE__*/React.createElement("h3", {
      className: "text-3xl font-semibold text-[#11446E]"
    }, flow.title), /*#__PURE__*/React.createElement("p", {
      className: "text-[#40566C] leading-relaxed"
    }, flow.description), /*#__PURE__*/React.createElement("ul", {
      className: "space-y-3 text-[#46617A]"
    }, flow.bullets.map(function (bullet) {
      return /*#__PURE__*/React.createElement("li", {
        key: bullet,
        className: "flex items-start gap-3"
      }, /*#__PURE__*/React.createElement("span", {
        className: "text-[#60B97B] mt-0.5"
      }, "\u2714"), /*#__PURE__*/React.createElement("span", null, bullet));
    }))), /*#__PURE__*/React.createElement("div", {
      className: "relative rounded-3xl overflow-hidden border border-[#D9E8F5] bg-white shadow-[0_22px_60px_rgba(17,68,110,0.12)] parallax-card",
      "data-parallax": "tilt"
    }, /*#__PURE__*/React.createElement("img", {
      src: flow.screenshot,
      alt: "Vista previa del flujo ".concat(flow.title),
      className: "w-full h-full object-cover"
    }), /*#__PURE__*/React.createElement("div", {
      className: "pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-white via-white/60 to-transparent"
    }), /*#__PURE__*/React.createElement("div", {
      className: "pointer-events-none absolute top-4 left-4 inline-flex items-center gap-2 rounded-full bg-white/90 px-4 py-2 text-xs font-semibold text-[#11446E] shadow-[0_12px_30px_rgba(17,68,110,0.12)]"
    }, /*#__PURE__*/React.createElement("span", {
      className: "h-2.5 w-2.5 rounded-full bg-[#2D6DAA]"
    }), "Vista previa del flujo")));
  }))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 py-24 px-8 bg-white",
    id: "screens"
  }, /*#__PURE__*/React.createElement("div", {
    className: "pointer-events-none absolute inset-x-24 -top-20 h-48 bg-gradient-to-b from-[#E8F6EE] via-transparent to-transparent blur-2xl opacity-80"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto text-center mb-14 reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-4xl font-bold mb-4 bg-gradient-to-r from-[#84D8A8] to-[#3C7FC0] text-transparent bg-clip-text"
  }, "Una vista al copiloto en acci\xF3n"), /*#__PURE__*/React.createElement("p", {
    className: "text-[#40566C] text-lg max-w-3xl mx-auto"
  }, "As\xED luce ContaFlow cuando captura, concilia y reporta con IA. Paneles pensados para que tu equipo solo valide excepciones.")), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto grid gap-10 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 reveal-on-scroll",
    "data-animate": "reveal"
  }, uiShowcase.map(function (item) {
    return /*#__PURE__*/React.createElement("div", {
      key: item.title,
      className: "group flex flex-col gap-5 rounded-3xl border border-[#D9E8F5] bg-white/95 p-5 shadow-[0_20px_50px_rgba(17,68,110,0.12)] transition hover:shadow-[0_28px_70px_rgba(17,68,110,0.18)]"
    }, /*#__PURE__*/React.createElement("div", {
      className: "relative overflow-hidden rounded-2xl border border-[#E1EFFC] bg-white"
    }, /*#__PURE__*/React.createElement("img", {
      src: item.image,
      alt: item.title,
      className: "w-full h-56 object-cover transition duration-300 group-hover:scale-[1.02]"
    }), /*#__PURE__*/React.createElement("div", {
      className: "pointer-events-none absolute top-4 left-4 inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-[#11446E] shadow-[0_10px_30px_rgba(17,68,110,0.12)]"
    }, "Vista previa")), /*#__PURE__*/React.createElement("div", {
      className: "space-y-2"
    }, /*#__PURE__*/React.createElement("h3", {
      className: "text-lg font-semibold text-[#11446E]"
    }, item.title), /*#__PURE__*/React.createElement("p", {
      className: "text-sm text-[#46617A] leading-relaxed"
    }, item.caption)));
  }))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 py-24 px-8 bg-white",
    id: "timeline"
  }, /*#__PURE__*/React.createElement("div", {
    className: "timeline-progress-track hidden md:block",
    "data-animate": "timeline-progress"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-5xl mx-auto text-center mb-14 reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-4xl font-bold mb-4 text-[#11446E]"
  }, "De onboarding a contabilidad aut\xF3noma en 4 pasos"), /*#__PURE__*/React.createElement("p", {
    className: "text-[#40566C]"
  }, "Implementar ContaFlow no requiere proyectos eternos. Este es el recorrido de cualquier empresa que se suma a la beta.")), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-5xl mx-auto space-y-12"
  }, timeline.map(function (step, index) {
    var isLast = index === timeline.length - 1;
    return /*#__PURE__*/React.createElement("div", {
      key: step.title,
      className: "relative flex items-start gap-5 reveal-on-scroll",
      "data-animate": "reveal"
    }, /*#__PURE__*/React.createElement("div", {
      className: "flex flex-col items-center"
    }, /*#__PURE__*/React.createElement("div", {
      className: "w-12 h-12 rounded-full bg-gradient-to-br from-[#E6F7EE] to-[#E6F1FD] border border-[#2D6DAA]/40 flex items-center justify-center text-[#11446E] font-semibold shadow-[0_10px_30px_rgba(17,68,110,0.12)]"
    }, index + 1), !isLast && /*#__PURE__*/React.createElement("div", {
      className: "hidden md:block w-px flex-1 bg-gradient-to-b from-[#2D6DAA]/35 via-[#60B97B]/25 to-transparent mt-3"
    })), /*#__PURE__*/React.createElement("div", {
      className: "flex-1 border border-[#D9E8F5] rounded-2xl px-6 py-5 bg-white shadow-[0_16px_40px_rgba(17,68,110,0.08)]"
    }, /*#__PURE__*/React.createElement("h3", {
      className: "text-xl font-semibold text-[#11446E] mb-2"
    }, step.title), /*#__PURE__*/React.createElement("p", {
      className: "text-[#40566C]"
    }, step.description)));
  }))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 py-24 px-8 bg-white overflow-hidden",
    id: "stories"
  }, /*#__PURE__*/React.createElement("div", {
    className: "pointer-events-none absolute -bottom-24 left-20 w-80 h-80 rounded-full bg-gradient-to-tr from-[#E6F1FD] via-transparent to-[#E8F6EE] blur-3xl opacity-80"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto text-center mb-14 reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-4xl font-bold mb-4 bg-gradient-to-r from-[#84D8A8] to-[#3C7FC0] text-transparent bg-clip-text"
  }, "Historias reales de despachos y CFOs"), /*#__PURE__*/React.createElement("p", {
    className: "text-[#40566C] max-w-3xl mx-auto"
  }, "ContaFlow naci\xF3 trabajando junto a despachos top y \xE1reas financieras exigentes. As\xED describen su nueva forma de trabajar.")), /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-6xl mx-auto grid md:grid-cols-3 gap-10"
  }, [{
    quote: "Reducimos 80% del trabajo repetitivo. Cada póliza viene con explicación en español claro lista para auditoría.",
    author: "Laura Hernández",
    role: "Socia, Despacho Fiscalista MX"
  }, {
    quote: "Antes requeríamos tres personas para conciliar dos bancos. Ahora el copiloto lo hace solo y aprobamos excepciones.",
    author: "Gustavo López",
    role: "CFO, Scale-up logística"
  }, {
    quote: "Los cierres dejaron de ser una crisis. Los reportes conectados al SAT salen listos sin perseguir tickets.",
    author: "María Torres",
    role: "Contadora corporativa, Grupo Retail"
  }].map(function (testimonial) {
    return /*#__PURE__*/React.createElement("div", {
      key: testimonial.author,
      className: "bg-white/95 backdrop-blur border border-[#D9E8F5] rounded-3xl p-8 shadow-[0_22px_60px_rgba(17,68,110,0.12)] reveal-on-scroll",
      "data-animate": "reveal"
    }, /*#__PURE__*/React.createElement("p", {
      className: "text-[#415F78] italic mb-6 leading-relaxed"
    }, "\u201C", testimonial.quote, "\u201D"), /*#__PURE__*/React.createElement("div", {
      className: "text-sm text-[#5F7990]"
    }, /*#__PURE__*/React.createElement("p", {
      className: "text-[#11446E] font-semibold"
    }, testimonial.author), /*#__PURE__*/React.createElement("p", null, testimonial.role)));
  }))), /*#__PURE__*/React.createElement("section", {
    className: "relative z-10 py-32 px-8 bg-white",
    id: "cta"
  }, /*#__PURE__*/React.createElement("div", {
    className: "relative max-w-4xl mx-auto"
  }, /*#__PURE__*/React.createElement("div", {
    className: "absolute inset-0 rounded-[36px] bg-gradient-to-r from-[#60B97B] via-[#2D6DAA] to-[#11446E] opacity-30 blur-2xl"
  }), /*#__PURE__*/React.createElement("div", {
    className: "relative text-center border border-[#D9E8F5] rounded-[32px] bg-white/95 px-10 md:px-16 py-16 shadow-[0_28px_70px_rgba(17,68,110,0.14)] cta-card reveal-on-scroll",
    "data-animate": "reveal"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-4xl md:text-5xl font-bold mb-6 leading-snug bg-gradient-to-r from-[#11446E] via-[#2D6DAA] to-[#60B97B] text-transparent bg-clip-text"
  }, "Da el salto a la contabilidad aut\xF3noma con IA explicable"), /*#__PURE__*/React.createElement("p", {
    className: "text-lg text-[#40566C] mb-10"
  }, "\xDAnete a la beta privada y descubre c\xF3mo ContaFlow libera horas de tu equipo y documenta cada decisi\xF3n para auditor\xEDas sin estr\xE9s."), /*#__PURE__*/React.createElement("div", {
    className: "flex flex-col sm:flex-row gap-4 justify-center"
  }, /*#__PURE__*/React.createElement(PillButton, {
    href: "https://cal.com/"
  }, "Agendar demo"), /*#__PURE__*/React.createElement(PillButton, {
    variant: "ghost",
    href: "/auth-login.html"
  }, "Crear cuenta beta"))))), /*#__PURE__*/React.createElement("footer", {
    className: "relative z-10 py-12 text-center text-[#5F7990] text-xs border-t border-[#D9E8F5] bg-white"
  }, /*#__PURE__*/React.createElement("img", {
    src: "/static/img/ContaFlow.png",
    alt: "ContaFlow Logo",
    width: 150,
    height: 60,
    className: "mx-auto mb-4"
  }), /*#__PURE__*/React.createElement("p", {
    className: "uppercase tracking-[0.35em] text-[#2D6DAA] mb-3"
  }, "ContaFlow \xB7 ERP & Contabilidad Aut\xF3noma"), /*#__PURE__*/React.createElement("p", {
    className: "text-[#46617A]"
  }, "\xA9 2025 ContaFlow \u2014 Reinventando la contabilidad con inteligencia artificial."), /*#__PURE__*/React.createElement("div", {
    className: "flex justify-center items-center gap-4 mt-4 text-[#6B859C]"
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    className: "hover:text-[#11446E] transition-colors"
  }, "Aviso de privacidad"), /*#__PURE__*/React.createElement("a", {
    href: "#",
    className: "hover:text-[#11446E] transition-colors"
  }, "T\xE9rminos del servicio"), /*#__PURE__*/React.createElement("a", {
    href: "mailto:hola@contaflow.ai",
    className: "hover:text-[#11446E] transition-colors"
  }, "hola@contaflow.ai"))));
};
window.ContaFlowLanding = ContaFlowLanding;
