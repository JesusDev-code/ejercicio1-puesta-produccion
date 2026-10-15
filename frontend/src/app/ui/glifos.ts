import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, input, signal } from '@angular/core';

const CARACTERES = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン0123456789';

interface Glifo {
  x: number;
  y: number;
  tam: number;
  color: string;
  dur: number;
  retraso: number;
  c: string;
}

function caracter(): string {
  return CARACTERES[Math.floor(Math.random() * CARACTERES.length)];
}

function glifo(): Glifo {
  const r = Math.random;
  const oro = r() < 0.2;
  return {
    x: r() * 98,
    y: r() * 96,
    tam: Math.round(11 + r() * 11),
    color: oro ? 'rgba(240,201,135,.45)' : 'rgba(255,77,94,.5)',
    dur: 4 + r() * 6,
    retraso: -r() * 10,
    c: caracter(),
  };
}

/**
 * Katakana y dígitos que aparecen, brillan y se desvanecen (no caen como lluvia).
 * Los estilos van por enlace de propiedades (CSSOM), no por atributo `style`, así que la CSP
 * no necesita 'unsafe-inline'.
 */
@Component({
  selector: 'app-glifos',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { 'aria-hidden': 'true' },
  template: `
    @for (g of glifos(); track $index) {
      <span
        class="glifo"
        [style.left.%]="g.x"
        [style.top.%]="g.y"
        [style.font-size.px]="g.tam"
        [style.color]="g.color"
        [style.text-shadow]="'0 0 14px ' + g.color"
        [style.animation-duration.s]="g.dur"
        [style.animation-delay.s]="g.retraso"
        >{{ g.c }}</span
      >
    }
  `,
  styles: `
    :host {
      position: absolute;
      inset: 0;
      overflow: hidden;
      pointer-events: none;
    }
    .glifo {
      position: absolute;
      font-family: var(--mono);
      opacity: 0;
      animation-name: aparecer;
      animation-iteration-count: infinite;
      animation-timing-function: ease-in-out;
      will-change: opacity;
    }
    @keyframes aparecer {
      0% { opacity: 0; transform: translateY(6px) scale(0.9); filter: blur(3px); }
      14% { opacity: 1; transform: none; filter: blur(0); }
      55% { opacity: 0.65; }
      100% { opacity: 0; transform: translateY(-4px); filter: blur(2px); }
    }
    @media (prefers-reduced-motion: reduce) {
      .glifo { animation: none; opacity: 0.2; }
    }
  `,
})
export class Glifos implements OnInit {
  readonly densidad = input(30);
  protected readonly glifos = signal<Glifo[]>([]);
  private readonly destroyRef = inject(DestroyRef);

  ngOnInit(): void {
    this.glifos.set(Array.from({ length: this.densidad() }, glifo));
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const t = setInterval(() => {
      this.glifos.update((lista) => {
        const copia = [...lista];
        for (let k = 0; k < 3; k++) {
          const i = Math.floor(Math.random() * copia.length);
          copia[i] = { ...copia[i], c: caracter() };
        }
        return copia;
      });
    }, 700);
    this.destroyRef.onDestroy(() => clearInterval(t));
  }
}
