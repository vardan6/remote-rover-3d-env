#version 130

struct p3d_LightSourceParameters {
    vec4 diffuse;
    vec4 position;
    sampler2DShadow shadowMap;
    mat4 shadowViewMatrix;
};
struct p3d_LightModelParameters {
    vec4 ambient;   // combined contribution from all AmbientLight nodes
};

uniform p3d_LightSourceParameters p3d_LightSource[1];
uniform p3d_LightModelParameters  p3d_LightModel;

in vec4 vColor;
in vec3 vNormal;
in vec4 vShadowCoord;

out vec4 fragColor;

// ------------------------------------------------------------
// 16-sample Poisson disk — well-spread, no obvious pattern
// ------------------------------------------------------------
const vec2 disk[16] = vec2[](
    vec2(-0.94201624, -0.39906216),
    vec2( 0.94558609, -0.76890725),
    vec2(-0.09418410, -0.92938870),
    vec2( 0.34495938,  0.29387760),
    vec2(-0.91588581,  0.45771432),
    vec2(-0.81544232, -0.87912464),
    vec2(-0.38277543,  0.27676845),
    vec2( 0.97484398,  0.75648379),
    vec2( 0.44323325, -0.97511554),
    vec2( 0.53742981, -0.47373420),
    vec2(-0.26496911, -0.41893023),
    vec2( 0.79197514,  0.19090188),
    vec2(-0.24188840,  0.99706507),
    vec2(-0.81409955,  0.91437590),
    vec2( 0.19984126,  0.78641367),
    vec2( 0.14383161, -0.14100790)
);

// ------------------------------------------------------------
// PCF shadow sampling
//   blurRadius — spread of the Poisson disk in texture space.
//   At 4096×4096 / 160 world-unit film → 1 texel ≈ 0.000244 UV.
//   0.001 ≈ 4-texel radius → ~16 cm clean soft penumbra (one shadow, no blobs).
// ------------------------------------------------------------
float sampleShadow(vec4 coord, float blurRadius) {
    // Perspective divide → [0,1] shadow-map texture space
    vec3 sc = coord.xyz / coord.w;

    float lit = 0.0;
    for (int i = 0; i < 16; i++) {
        // Offset only s,t — keep depth (sc.z) fixed for correct comparison
        lit += texture(p3d_LightSource[0].shadowMap,
                       sc + vec3(disk[i] * blurRadius, 0.0));
    }
    return lit / 16.0;
}

void main() {
    vec3  N        = normalize(vNormal);
    vec3  L        = normalize(p3d_LightSource[0].position.xyz); // toward sun, view-space
    float diff     = max(dot(N, L), 0.0);
    float shadow   = sampleShadow(vShadowCoord, 0.001);

    vec4 ambient   = p3d_LightModel.ambient              * vColor;
    vec4 diffuse   = p3d_LightSource[0].diffuse * diff * shadow * vColor;

    fragColor   = clamp(ambient + diffuse, 0.0, 1.0);
    fragColor.a = vColor.a;
}
