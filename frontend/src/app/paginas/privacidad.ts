import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Marca } from '../ui/marca';

/**
 * Política de privacidad pública: la exige Google para publicar el login con Google, y describe
 * lo que la app hace de verdad (docs/UMBRAL.md, sección 10). Si cambia lo que se guarda, cambia aquí.
 */
@Component({
  selector: 'app-privacidad',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Marca],
  template: `
    <div class="pagina">
      <header class="cabecera">
        <a routerLink="/" aria-label="Volver a la web de Kaelum Security"><app-marca [tam]="32" nombre="Kaelum" subtitulo="SECURITY · UMBRAL" /></a>
      </header>

      <main class="contenido">
        <span class="etiqueta-mono">LEGAL</span>
        <h1 class="titulo">Política de privacidad</h1>
        <p class="aviso-ficticio">
          Kaelum Security es una empresa ficticia y Umbral un proyecto académico de Puesta en producción segura. No se presta
          ningún servicio real. Aun así, esta política describe con exactitud qué datos trata la aplicación.
        </p>

        <section aria-labelledby="p-que">
          <h2 id="p-que">Qué datos se guardan</h2>
          <ul>
            <li><strong>Cuenta:</strong> email, rol, empresa a la que perteneces y si la cuenta está activa.</li>
            <li><strong>Contraseña:</strong> solo un hash Argon2id. Nunca se guarda en claro. Las cuentas creadas con Google o GitHub no tienen contraseña.</li>
            <li>
              <strong>Google o GitHub:</strong> si entras con ellos, solo se guardan el identificador de tu cuenta en ese proveedor y
              tu email verificado. No se pide acceso a tus contactos, archivos, repositorios ni a nada más.
            </li>
            <li><strong>Verificación en dos pasos:</strong> el secreto de tu app de autenticación, cifrado, y el hash de tus códigos de recuperación.</li>
            <li><strong>Sesiones:</strong> el hash de los tokens de refresco, con su caducidad.</li>
            <li><strong>Incidencias</strong> que reportes o gestiones, con sus notas.</li>
            <li><strong>Auditoría:</strong> quién hizo qué acción, sobre qué recurso, desde qué IP y cuándo, incluidos los intentos de acceso fallidos.</li>
            <li>
              <strong>Eventos de los sensores:</strong> IP de origen, ruta, método y user-agent de quien sondea los señuelos, con
              finalidad de seguridad.
            </li>
          </ul>
        </section>

        <section aria-labelledby="p-cuanto">
          <h2 id="p-cuanto">Cuánto tiempo</h2>
          <ul>
            <li>Los datos de la cuenta, mientras exista la cuenta.</li>
            <li>Los eventos de los sensores, 30 días, salvo los enlazados a una incidencia, que se conservan como evidencia.</li>
            <li>Las copias de seguridad, 7 días.</li>
            <li>Las incidencias y la auditoría, de forma indefinida: el borrado de incidencias es lógico.</li>
          </ul>
        </section>

        <section aria-labelledby="p-terceros">
          <h2 id="p-terceros">Con quién se comparten</h2>
          <p>
            Con nadie. No hay analítica, publicidad ni recursos cargados desde otros dominios. Google y GitHub solo intervienen si
            eliges entrar con ellos, y solo para confirmar tu identidad.
          </p>
        </section>

        <section aria-labelledby="p-cookies">
          <h2 id="p-cookies">Cookies</h2>
          <p>
            Solo cookies técnicas imprescindibles: la de la sesión (para no pedirte la contraseña en cada visita) y, durante 10
            minutos, la del inicio de sesión con Google o GitHub. Ninguna de seguimiento.
          </p>
        </section>

        <section aria-labelledby="p-derechos">
          <h2 id="p-derechos">Tus derechos</h2>
          <p>
            Puedes pedir acceder a tus datos, rectificarlos o suprimirlos, y ejercer el resto de derechos que te reconoce el RGPD,
            escribiendo al administrador de la plataforma.
          </p>
        </section>

        <p class="volver"><a routerLink="/">← Volver a Kaelum Security</a></p>
      </main>
    </div>
  `,
  styles: `
    .pagina { min-height: 100vh; padding: 32px 48px 56px; }
    .cabecera a { text-decoration: none; display: inline-block; }
    .contenido { max-width: 760px; margin: 40px auto 0; display: flex; flex-direction: column; gap: 22px; line-height: 1.7; }
    .titulo { font-family: var(--serif); font-size: 44px; font-weight: 600; line-height: 1.1; }
    h2 { font-size: 19px; font-weight: 700; margin-bottom: 6px; }
    ul { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 6px; }
    p, li { font-size: 15px; color: var(--apagado); }
    .aviso-ficticio { color: var(--tenue); font-size: 14px; }
    .volver a { color: var(--oro-claro); }
    @media (max-width: 720px) { .pagina { padding: 24px 16px 40px; } .titulo { font-size: 34px; } }
  `,
})
export class Privacidad {}
