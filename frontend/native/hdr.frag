#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float whiteScale;
    float hdrActive;
    float highlightBoost;
    vec2 texelSize;
};
layout(binding = 1) uniform sampler2D source;
float emitter(vec3 s) {
    return smoothstep(0.10, 0.42, s.b - s.r) * smoothstep(0.60, 0.96, s.b);
}
vec3 emission(vec2 uv) {
    vec3 s = texture(source, uv).rgb;
    return s * s * emitter(s);
}
void main() {
    vec4 pixel = texture(source, qt_TexCoord0);
    // A missing native texture must never replace the live workspace with a
    // blank rectangle. Keep the directly rendered WebEngine node underneath.
    if (pixel.a < 0.001) {fragColor = vec4(0.0);return;}
    if (hdrActive < 0.5) {
        fragColor = pixel * qt_Opacity;
        return;
    }
    vec3 s = pixel.rgb / max(pixel.a, 0.0001);
    vec3 linear = mix(s / 12.92, pow((s + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), s));
    // Neutral text stays at paper white. Colored rims, controls and selections
    // emit above it; a four-tap local halo needs no extra render target/canvas.
    float accent = emitter(s);
    linear *= whiteScale * (1.0 + highlightBoost * accent);
    if (highlightBoost > 0.001) {
        vec2 offset = texelSize * 3.0;
        vec3 glow = emission(qt_TexCoord0 + vec2(offset.x, 0.0)) + emission(qt_TexCoord0 - vec2(offset.x, 0.0))
                  + emission(qt_TexCoord0 + vec2(0.0, offset.y)) + emission(qt_TexCoord0 - vec2(0.0, offset.y));
        linear += glow * whiteScale * highlightBoost * 0.028;
    }
    fragColor = vec4(min(linear, vec3(8.0)), 1.0) * qt_Opacity;
}
