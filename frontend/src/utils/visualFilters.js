import * as Cesium from "cesium";

/**
 * Creates a CRT (cathode-ray tube) post-process stage with scanlines,
 * barrel distortion, chromatic aberration, vignette, and green phosphor tint.
 */
export function createCRTStage() {
  return new Cesium.PostProcessStage({
    name: "crt_filter",
    fragmentShader: `
      uniform sampler2D colorTexture;
      in vec2 v_textureCoordinates;

      void main() {
        vec2 uv = v_textureCoordinates;

        // Barrel distortion (subtle)
        vec2 offset = uv - 0.5;
        float distSq = dot(offset, offset);
        vec2 distortedUV = uv + offset * distSq * 0.04;

        // Chromatic aberration
        float aberration = 0.001;
        float r = texture(colorTexture, distortedUV + vec2( aberration, 0.0)).r;
        float g = texture(colorTexture, distortedUV).g;
        float b = texture(colorTexture, distortedUV + vec2(-aberration, 0.0)).b;
        vec3 color = vec3(r, g, b);

        // Scanlines
        float scanline = 1.0 - sin(gl_FragCoord.y * 1.5) * 0.08;
        color *= scanline;

        // Vignette
        float vignette = smoothstep(0.8, 0.4, length(uv - 0.5));
        color *= vignette;

        // Green phosphor tint
        color *= vec3(0.9, 1.0, 0.9);

        out_FragColor = vec4(color, 1.0);
      }
    `,
  });
}

/**
 * Creates a night-vision goggle (NVG) composite with green monochrome,
 * animated film grain, and bloom glow.
 */
export function createNVGStage() {
  const nvgMain = new Cesium.PostProcessStage({
    name: "nvg_main",
    fragmentShader: `
      uniform sampler2D colorTexture;
      in vec2 v_textureCoordinates;

      void main() {
        vec2 uv = v_textureCoordinates;
        vec4 texel = texture(colorTexture, uv);

        float lum = dot(texel.rgb, vec3(0.299, 0.587, 0.114));

        // Animated film grain
        float grain = fract(
          sin(dot(uv * czm_frameNumber, vec2(12.9898, 78.233))) * 43758.5453
        );
        lum += (grain - 0.5) * 0.12;

        // Green NVG tint
        vec3 color = vec3(0.1, 1.0, 0.1) * lum;

        // Vignette
        float vignette = smoothstep(0.9, 0.4, length(uv - 0.5));
        color *= vignette;

        out_FragColor = vec4(color, 1.0);
      }
    `,
  });

  const nvgBloom = new Cesium.PostProcessStage({
    name: "nvg_bloom",
    fragmentShader: `
      uniform sampler2D colorTexture;
      in vec2 v_textureCoordinates;

      void main() {
        vec2 uv = v_textureCoordinates;
        vec2 texelSize = 1.0 / vec2(textureSize(colorTexture, 0));

        vec3 center = texture(colorTexture, uv).rgb;
        vec3 blur =
          texture(colorTexture, uv + vec2(-texelSize.x, 0.0)).rgb +
          texture(colorTexture, uv + vec2( texelSize.x, 0.0)).rgb +
          texture(colorTexture, uv + vec2(0.0, -texelSize.y)).rgb +
          texture(colorTexture, uv + vec2(0.0,  texelSize.y)).rgb;
        blur *= 0.25;

        float brightness = dot(center, vec3(0.333));
        vec3 glow = blur * smoothstep(0.3, 0.8, brightness) * 0.6;

        out_FragColor = vec4(center + glow, 1.0);
      }
    `,
  });

  return new Cesium.PostProcessStageComposite({
    name: "nvg_filter",
    stages: [nvgMain, nvgBloom],
    inputPreviousStageTexture: true,
  });
}

/**
 * Creates a FLIR / thermal post-process stage with Iron Bow color palette
 * and slight Gaussian blur.
 */
export function createFLIRStage() {
  return new Cesium.PostProcessStage({
    name: "flir_filter",
    fragmentShader: `
      uniform sampler2D colorTexture;
      in vec2 v_textureCoordinates;

      vec3 ironBow(float t) {
        if (t < 0.15) {
          return mix(vec3(0.0), vec3(0.0, 0.0, 0.3), t / 0.15);
        } else if (t < 0.35) {
          return mix(vec3(0.0, 0.0, 0.3), vec3(0.5, 0.0, 0.5), (t - 0.15) / 0.2);
        } else if (t < 0.55) {
          return mix(vec3(0.5, 0.0, 0.5), vec3(0.9, 0.1, 0.0), (t - 0.35) / 0.2);
        } else if (t < 0.75) {
          return mix(vec3(0.9, 0.1, 0.0), vec3(1.0, 0.5, 0.0), (t - 0.55) / 0.2);
        } else if (t < 0.9) {
          return mix(vec3(1.0, 0.5, 0.0), vec3(1.0, 1.0, 0.0), (t - 0.75) / 0.15);
        } else {
          return mix(vec3(1.0, 1.0, 0.0), vec3(1.0), (t - 0.9) / 0.1);
        }
      }

      void main() {
        vec2 uv = v_textureCoordinates;
        vec2 texelSize = 1.0 / vec2(textureSize(colorTexture, 0));

        // 5-tap Gaussian blur for thermal softness
        vec3 blurred =
          texture(colorTexture, uv).rgb * 0.5 +
          texture(colorTexture, uv + vec2(texelSize.x, 0.0)).rgb * 0.125 +
          texture(colorTexture, uv - vec2(texelSize.x, 0.0)).rgb * 0.125 +
          texture(colorTexture, uv + vec2(0.0, texelSize.y)).rgb * 0.125 +
          texture(colorTexture, uv - vec2(0.0, texelSize.y)).rgb * 0.125;

        float lum = dot(blurred, vec3(0.299, 0.587, 0.114));
        lum = clamp(lum, 0.0, 1.0);

        vec3 thermal = ironBow(lum);

        out_FragColor = vec4(thermal, 1.0);
      }
    `,
  });
}

/**
 * Creates a cel-shading / Studio Ghibli anime style composite with
 * Sobel edge detection, color quantization, and warm color grading.
 */
export function createAnimeStage() {
  const animeMain = new Cesium.PostProcessStage({
    name: "anime_main",
    fragmentShader: `
      uniform sampler2D colorTexture;
      in vec2 v_textureCoordinates;

      void main() {
        vec2 uv = v_textureCoordinates;
        vec2 texelSize = 1.0 / vec2(textureSize(colorTexture, 0));

        // Sobel edge detection
        vec3 tl = texture(colorTexture, uv + vec2(-texelSize.x, texelSize.y)).rgb;
        vec3 t  = texture(colorTexture, uv + vec2(0.0, texelSize.y)).rgb;
        vec3 tr = texture(colorTexture, uv + vec2(texelSize.x, texelSize.y)).rgb;
        vec3 l  = texture(colorTexture, uv + vec2(-texelSize.x, 0.0)).rgb;
        vec3 r  = texture(colorTexture, uv + vec2(texelSize.x, 0.0)).rgb;
        vec3 bl = texture(colorTexture, uv + vec2(-texelSize.x, -texelSize.y)).rgb;
        vec3 b  = texture(colorTexture, uv + vec2(0.0, -texelSize.y)).rgb;
        vec3 br = texture(colorTexture, uv + vec2(texelSize.x, -texelSize.y)).rgb;

        vec3 gx = -tl - 2.0*l - bl + tr + 2.0*r + br;
        vec3 gy = -tl - 2.0*t - tr + bl + 2.0*b + br;
        float edge = length(gx) + length(gy);

        // Color quantization (reduce to ~8 levels per channel for cel look)
        vec3 color = texture(colorTexture, uv).rgb;
        color = floor(color * 6.0 + 0.5) / 6.0;

        // Boost saturation for anime vibrance
        float gray = dot(color, vec3(0.299, 0.587, 0.114));
        color = mix(vec3(gray), color, 1.5);

        // Draw black outlines where edges are strong
        float outline = smoothstep(0.3, 0.8, edge);
        color = mix(color, vec3(0.05), outline);

        out_FragColor = vec4(color, 1.0);
      }
    `,
  });

  const animeGrade = new Cesium.PostProcessStage({
    name: "anime_grade",
    fragmentShader: `
      uniform sampler2D colorTexture;
      in vec2 v_textureCoordinates;

      void main() {
        vec2 uv = v_textureCoordinates;
        vec3 color = texture(colorTexture, uv).rgb;

        // Warm Studio Ghibli color shift
        color.r = pow(color.r, 0.9);
        color.g = pow(color.g, 0.95);
        color.b = pow(color.b, 1.1);

        // Slight bloom on bright areas
        float bright = max(max(color.r, color.g), color.b);
        color += color * smoothstep(0.6, 1.0, bright) * 0.2;

        out_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
      }
    `,
  });

  return new Cesium.PostProcessStageComposite({
    name: "anime_filter",
    stages: [animeMain, animeGrade],
    inputPreviousStageTexture: true,
  });
}

/**
 * Creates a military targeting reticle HUD overlay with crosshairs,
 * range rings, tick marks, center dot, and corner brackets.
 */
export function createReticleStage() {
  return new Cesium.PostProcessStage({
    name: "reticle_filter",
    fragmentShader: `
      uniform sampler2D colorTexture;
      in vec2 v_textureCoordinates;

      void main() {
        vec2 uv = v_textureCoordinates;
        vec3 color = texture(colorTexture, uv).rgb;

        vec2 center = vec2(0.5);
        vec2 pos = uv - center;
        float dist = length(pos);
        float angle = atan(pos.y, pos.x);

        vec3 hud = vec3(0.0, 1.0, 0.4); // green HUD color
        float alpha = 0.0;

        // Crosshair lines (thin)
        float crossH = step(abs(pos.y), 0.001) * step(0.02, abs(pos.x)) * step(abs(pos.x), 0.15);
        float crossV = step(abs(pos.x), 0.001) * step(0.02, abs(pos.y)) * step(abs(pos.y), 0.15);
        alpha += (crossH + crossV) * 0.8;

        // Range rings
        for (int i = 1; i <= 3; i++) {
          float r = float(i) * 0.08;
          float ring = smoothstep(0.001, 0.0, abs(dist - r) - 0.0008);
          alpha += ring * 0.5;
        }

        // Tick marks on outer ring (every 30 degrees)
        float outerR = 0.24;
        float outerRing = smoothstep(0.001, 0.0, abs(dist - outerR) - 0.0008);
        alpha += outerRing * 0.4;

        // Tick marks at cardinal directions
        for (int i = 0; i < 12; i++) {
          float a = float(i) * 3.14159265 / 6.0;
          float tickDist = abs(angle - a);
          tickDist = min(tickDist, abs(angle - a + 6.28318));
          tickDist = min(tickDist, abs(angle - a - 6.28318));
          if (tickDist < 0.03 && dist > 0.22 && dist < 0.26) {
            alpha += 0.6;
          }
        }

        // Center dot
        float centerDot = smoothstep(0.004, 0.002, dist);
        alpha += centerDot * 0.9;

        // Corner brackets (top-left, top-right, bottom-left, bottom-right)
        float bracketSize = 0.06;
        float bracketThick = 0.002;
        float margin = 0.3;

        // Top-left bracket
        if (uv.x > (0.5 - margin) && uv.x < (0.5 - margin + bracketSize) && abs(uv.y - (0.5 + margin)) < bracketThick) alpha += 0.7;
        if (uv.y < (0.5 + margin) && uv.y > (0.5 + margin - bracketSize) && abs(uv.x - (0.5 - margin)) < bracketThick) alpha += 0.7;
        // Top-right bracket
        if (uv.x < (0.5 + margin) && uv.x > (0.5 + margin - bracketSize) && abs(uv.y - (0.5 + margin)) < bracketThick) alpha += 0.7;
        if (uv.y < (0.5 + margin) && uv.y > (0.5 + margin - bracketSize) && abs(uv.x - (0.5 + margin)) < bracketThick) alpha += 0.7;
        // Bottom-left bracket
        if (uv.x > (0.5 - margin) && uv.x < (0.5 - margin + bracketSize) && abs(uv.y - (0.5 - margin)) < bracketThick) alpha += 0.7;
        if (uv.y > (0.5 - margin) && uv.y < (0.5 - margin + bracketSize) && abs(uv.x - (0.5 - margin)) < bracketThick) alpha += 0.7;
        // Bottom-right bracket
        if (uv.x < (0.5 + margin) && uv.x > (0.5 + margin - bracketSize) && abs(uv.y - (0.5 - margin)) < bracketThick) alpha += 0.7;
        if (uv.y > (0.5 - margin) && uv.y < (0.5 - margin + bracketSize) && abs(uv.x - (0.5 + margin)) < bracketThick) alpha += 0.7;

        alpha = clamp(alpha, 0.0, 1.0);
        color = mix(color, hud, alpha * 0.85);

        out_FragColor = vec4(color, 1.0);
      }
    `,
  });
}

/**
 * Removes all custom visual filter stages from the viewer,
 * leaving built-in stages (FXAA) untouched.
 */
export function removeAllFilters(viewer) {
  const stages = viewer.scene.postProcessStages;
  const customNames = ["crt_filter", "nvg_filter", "flir_filter", "anime_filter", "reticle_filter"];

  for (let i = stages.length - 1; i >= 0; i--) {
    const stage = stages.get(i);
    if (customNames.includes(stage.name)) {
      stages.remove(stage);
    }
  }
}
