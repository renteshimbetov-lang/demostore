/**
 * BlurText Vanilla JavaScript Utility (from React Bits)
 * Works in any browser without React or bundlers.
 */
function createBlurText(container, options = {}) {
  if (!container) return;
  const {
    text = container.dataset.blurText || container.textContent || '',
    delay = 60,
    animateBy = 'letters', // 'letters' | 'words'
    direction = 'top',
    threshold = 0.1,
    rootMargin = '0px',
    onAnimationComplete
  } = options;

  container.innerHTML = '';
  container.classList.add('blur-text-wrap');

  const elements = animateBy === 'words' ? text.split(' ') : text.split('');
  let totalIndex = 0;

  const spans = elements.map((seg, idx) => {
    const span = document.createElement('span');
    span.className = `blur-letter ${direction === 'bottom' ? 'from-bottom' : ''}`;
    span.style.setProperty('--i', totalIndex++);
    span.textContent = seg === ' ' ? '\u00A0' : seg;
    if (animateBy === 'words' && idx < elements.length - 1) {
      span.textContent += '\u00A0';
    }
    span.style.animationDelay = `${idx * delay}ms`;
    container.appendChild(span);
    return span;
  });

  if (typeof onAnimationComplete === 'function' && spans.length > 0) {
    const lastSpan = spans[spans.length - 1];
    lastSpan.addEventListener('animationend', () => {
      onAnimationComplete();
    }, { once: true });
  }

  // IntersectionObserver trigger
  if ('IntersectionObserver' in window && threshold !== undefined) {
    container.style.opacity = '0';
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        container.style.opacity = '1';
        container.classList.add('in-view');
        observer.unobserve(container);
      }
    }, { threshold, rootMargin });
    observer.observe(container);
  }

  return {
    replay: () => {
      container.classList.add('animate-trigger');
      void container.offsetWidth; // reflow
      container.classList.remove('animate-trigger');
    }
  };
}

if (typeof window !== 'undefined') {
  window.createBlurText = createBlurText;
}
