import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Esqueleto mientras responde la API. */
@Component({
  selector: 'app-cargando',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <p class="etiqueta">Consultando la API<span class="cursor">_</span></p>
    <div aria-hidden="true" class="lineas">
      <div class="carga ancho-1"></div>
      <div class="carga ancho-2"></div>
      <div class="carga ancho-3"></div>
    </div>
  `,
  host: { role: 'status' },
  styles: `
    :host { display: flex; flex-direction: column; gap: 16px; padding: 24px; }
    .etiqueta { font-family: var(--serif); font-weight: 600; font-size: 26px; }
    .cursor { color: var(--sangre-claro); }
    .lineas { display: flex; flex-direction: column; gap: 10px; }
    .ancho-1 { width: 92%; } .ancho-2 { width: 74%; } .ancho-3 { width: 84%; }
  `,
})
export class Cargando {}

/** 404 y «no tienes acceso» se pintan igual: la interfaz nunca los distingue. */
@Component({
  selector: 'app-no-existe',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  template: `
    <section class="cristal tarjeta" aria-labelledby="t-404">
      <span class="pildora etiqueta-404">404 · no encontrado</span>
      <h2 id="t-404" class="titulo-2 grande">{{ titulo() }}</h2>
      <p class="subtitulo">Puede que nunca haya existido o que se haya borrado.</p>
      <a routerLink="/incidentes" class="btn btn-suave">Ir al listado</a>
    </section>
  `,
  styles: `
    .tarjeta { max-width: 560px; padding: 30px; display: flex; flex-direction: column; align-items: flex-start; gap: 14px; }
    .etiqueta-404 { background: rgba(255, 255, 255, 0.07); font-family: var(--mono); font-size: 11px; color: var(--texto-2); }
    .grande { font-size: 34px; }
  `,
})
export class NoExiste {
  readonly titulo = input('Este incidente no existe');
}

/** 500/503 o sin conexión. Nunca se muestran trazas ni detalles internos. */
@Component({
  selector: 'app-fallo-servidor',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="tarjeta" role="alert" aria-labelledby="t-500">
      <span class="pildora etiqueta-500">{{ codigo() === 0 ? 'sin conexión' : '500 / 503 · servidor' }}</span>
      <h2 id="t-500" class="titulo-2 grande">Algo ha fallado en el servidor</h2>
      <p class="texto">Si persiste, revisa el estado del servicio.</p>
      <button type="button" class="btn btn-peligro" (click)="reintentar.emit()">Reintentar</button>
    </section>
  `,
  styles: `
    .tarjeta {
      max-width: 560px; padding: 30px; border-radius: 24px; display: flex; flex-direction: column; align-items: flex-start; gap: 14px;
      background: linear-gradient(165deg, rgba(224, 30, 60, 0.16), rgba(224, 30, 60, 0.03));
      backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
      box-shadow: inset 0 1px 0 rgba(255, 180, 190, 0.12), 0 0 60px -20px rgba(224, 30, 60, 0.6);
    }
    .etiqueta-500 { background: rgba(224, 30, 60, 0.2); font-family: var(--mono); font-size: 11px; color: var(--sangre-rosa); }
    .grande { font-size: 34px; }
    .texto { font-size: 14px; line-height: 1.65; color: #e3c2c8; }
  `,
})
export class FalloServidor {
  readonly codigo = input(500);
  readonly reintentar = output();
}
