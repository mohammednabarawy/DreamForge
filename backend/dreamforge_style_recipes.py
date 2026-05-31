from __future__ import annotations

from typing import Any

STYLE_RECIPES: dict[str, dict[str, Any]] = {
    "image_edit": {
        "models": [
            "flux1-dev-kontext_fp8_scaled.safetensors"
        ],
        "notes": "Requires --input-image. Uses Flux Kontext for high-quality edits.",
        "thumbnail": "assets/style_thumbnails/image_edit.jpg"
    },
    "concept_art": {
        "styles": [],
        "performance": "HiDream",
        "aspect_ratio": "1152x896",
        "prompt_prefix": "Concept art illustration, detailed environment design",
        "models": [
            "hidream_o1_image_dev_mxfp8.safetensors"
        ],
        "thumbnail": "assets/style_thumbnails/concept_art.jpg"
    },
    "fast_draft": {
        "models": [
            "z_image_turbo_fp8_e4m3fn.safetensors",
            "flux1-schnell-fp8.safetensors"
        ],
        "performance": "Speed",
        "notes": "Fastest possible generation for iteration/previews.",
        "thumbnail": "assets/style_thumbnails/fast_draft.jpg"
    },
    "mockup_ui": {
        "models": [
            "flux1-schnell-fp8.safetensors"
        ],
        "styles": [],
        "performance": "Flux",
        "prompt_prefix": "Clean modern UI mockup, app interface design",
        "thumbnail": "assets/style_thumbnails/mockup_ui.jpg"
    },
    "product_ad": {
        "prompt_profile": "product_ad",
        "positive": [
            "premium product advertising campaign",
            "clear hero product",
            "intentional negative space",
            "commercial studio lighting",
            "high-end editorial composition"
        ],
        "styles": [
            "Style: ads-advertising",
            "Style: sai-photographic",
            "Style: sai-enhance"
        ],
        "models": [
            "juggernautXL_v8Rundiffusion.safetensors",
            "RealVisXL_V5.0_fp16.safetensors",
            "realisticStockPhoto_v20.safetensors"
        ],
        "performance": "Quality",
        "aspect_ratio": "1152x896",
        "prompt_prefix": "A professional product advertisement photograph, high-end commercial styling",
        "thumbnail": "assets/style_thumbnails/product_ad.jpg"
    },
    "book_cover": {
        "styles": [
            "Style: sai-cinematic",
            "Style: sai-enhance",
            "Style: artstyle-typography"
        ],
        "performance": "Quality",
        "aspect_ratio": "896x1344",
        "prompt_prefix": "An award-winning book cover illustration, dramatic composition",
        "thumbnail": "assets/style_thumbnails/book_cover.jpg"
    },
    "cinematic": {
        "styles": [
            "Style: sai-cinematic",
            "Style: photo-film noir",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1152x896",
        "prompt_prefix": "A cinematic movie still, 8k resolution, dramatic lighting, shot on 35mm lens",
        "thumbnail": "assets/style_thumbnails/cinematic.jpg"
    },
    "avatar_portrait": {
        "styles": [
            "Style: sai-photographic",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A professional avatar portrait, studio lighting, highly detailed face",
        "thumbnail": "assets/style_thumbnails/avatar_portrait.jpg"
    },
    "logo_mockup": {
        "styles": [
            "Style: ads-corporate",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A realistic corporate logo mockup, elegant minimal background",
        "thumbnail": "assets/style_thumbnails/logo_mockup.jpg"
    },
    "fashion_editorial": {
        "styles": [
            "Style: ads-fashion editorial",
            "Style: sai-photographic"
        ],
        "performance": "Quality",
        "aspect_ratio": "896x1152",
        "prompt_prefix": "High fashion editorial photography, Vogue magazine style",
        "thumbnail": "assets/style_thumbnails/fashion_editorial.jpg"
    },
    "real_estate": {
        "styles": [
            "Style: ads-real estate",
            "Style: misc-architectural",
            "Style: sai-photographic"
        ],
        "performance": "Quality",
        "aspect_ratio": "1344x896",
        "prompt_prefix": "Professional architectural photography, luxury real estate interior/exterior",
        "thumbnail": "assets/style_thumbnails/real_estate.jpg"
    },
    "game_asset": {
        "styles": [
            "Style: sai-fantasy art",
            "Style: game-rpg fantasy game",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A high-quality 2D game asset illustration, isolated, detailed concept art",
        "thumbnail": "assets/style_thumbnails/game_asset.jpg"
    },
    "youtube_thumbnail": {
        "styles": [
            "Style: sai-enhance",
            "Style: sai-digital art"
        ],
        "performance": "Speed",
        "aspect_ratio": "1280x720",
        "prompt_prefix": "An engaging YouTube thumbnail background, vibrant colors, high contrast",
        "thumbnail": "assets/style_thumbnails/youtube_thumbnail.jpg"
    },
    "pattern_texture": {
        "styles": [
            "Style: sai-texture",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A seamless texture pattern, flat lighting, perfect tiling",
        "thumbnail": "assets/style_thumbnails/pattern_texture.jpg"
    },
    "anime_illustration": {
        "styles": [
            "Style: sai-anime",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "896x1152",
        "prompt_prefix": "A high-quality anime illustration, studio ghibli style, detailed background",
        "thumbnail": "assets/style_thumbnails/anime_illustration.jpg"
    },
    "3d_render": {
        "styles": [
            "Style: sai-3d-model",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A high quality 3D render, octane render, unreal engine 5, ray tracing",
        "thumbnail": "assets/style_thumbnails/3d_render.jpg"
    },
    "app_icon": {
        "styles": [
            "Style: sai-digital art",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A modern flat mobile app icon design, clear silhouette, minimal",
        "thumbnail": "assets/style_thumbnails/app_icon.jpg"
    },
    "sticker_design": {
        "styles": [
            "Style: sai-digital art",
            "Style: sai-enhance"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A die-cut vinyl sticker design, white border contour, flat colors",
        "thumbnail": "assets/style_thumbnails/sticker_design.jpg"
    },
    "arabic_poster": {
        "prompt_profile": "nano_banana_pro",
        "positive": [
            "professional Arabic poster design",
            "clean readable headline area",
            "premium visual hierarchy",
            "blank surfaces reserved for exact text"
        ],
        "negative": [
            "fake Arabic",
            "random Latin letters",
            "duplicate text",
            "watermark",
            "logo unless provided"
        ],
        "styles": [
            "Style: sai-enhance"
        ],
        "models": [
            "RealVisXL_V5.0_fp16.safetensors",
            "juggernautXL_v8Rundiffusion.safetensors"
        ],
        "preset": "pro_text",
        "performance": "Quality",
        "steps": 45,
        "thumbnail": "assets/style_thumbnails/arabic_poster.jpg"
    },
    "social_post": {
        "prompt_profile": "image2",
        "positive": [
            "polished social media campaign visual",
            "bold central subject",
            "clean space for caption overlay",
            "high contrast composition"
        ],
        "negative": [
            "unreadable text",
            "watermark",
            "clutter",
            "low quality"
        ],
        "styles": [
            "Style: sai-enhance",
            "Style: sai-photographic"
        ],
        "models": [
            "juggernautXL_v8Rundiffusion.safetensors",
            "RealVisXL_V5.0_fp16.safetensors"
        ],
        "aspect_ratio": "1024x1024",
        "performance": "Speed",
        "thumbnail": "assets/style_thumbnails/social_post.jpg"
    },
    "thumbnail": {
        "prompt_profile": "image2",
        "positive": [
            "high-impact thumbnail composition",
            "large clear subject",
            "dramatic contrast",
            "simple readable background"
        ],
        "negative": [
            "tiny details",
            "unreadable text",
            "watermark",
            "busy background"
        ],
        "styles": [
            "Style: sai-enhance"
        ],
        "models": [
            "juggernautXL_v8Rundiffusion.safetensors",
            "epicrealismXL_vxiAbeast.safetensors"
        ],
        "aspect_ratio": "1280x768",
        "performance": "Speed",
        "thumbnail": "assets/style_thumbnails/thumbnail.jpg"
    },
    "cinematic_scene": {
        "prompt_profile": "cinematic",
        "positive": [
            "cinematic film still",
            "strong atmosphere",
            "professional color grading",
            "controlled depth of field"
        ],
        "negative": [
            "flat lighting",
            "watermark",
            "low quality",
            "bad anatomy"
        ],
        "styles": [],
        "models": [
            "hidream_o1_image_dev_mxfp8.safetensors",
            "epicrealismXL_vxiAbeast.safetensors",
            "juggernautXL_v8Rundiffusion.safetensors"
        ],
        "aspect_ratio": "1152x896",
        "performance": "HiDream",
        "steps": 28,
        "thumbnail": "assets/style_thumbnails/cinematic_scene.jpg"
    },
    "infographic": {
        "prompt_profile": "infographic",
        "positive": [
            "organized infographic background",
            "clear sections",
            "generous spacing",
            "clean modern layout"
        ],
        "negative": [
            "random text",
            "fake labels",
            "messy diagram",
            "watermark"
        ],
        "styles": [
            "Style: sai-enhance"
        ],
        "models": [
            "RealVisXL_V5.0_fp16.safetensors",
            "juggernautXL_v8Rundiffusion.safetensors"
        ],
        "aspect_ratio": "1152x896",
        "performance": "Speed",
        "thumbnail": "assets/style_thumbnails/infographic.jpg"
    },
    "signage": {
        "prompt_profile": "signage",
        "positive": [
            "realistic physical sign surface",
            "clear readable sign area",
            "believable reflections and shadows",
            "integrated environment"
        ],
        "negative": [
            "gibberish text",
            "extra letters",
            "duplicate text",
            "watermark"
        ],
        "styles": [
            "Style: sai-enhance"
        ],
        "models": [
            "juggernautXL_v8Rundiffusion.safetensors",
            "RealVisXL_V5.0_fp16.safetensors"
        ],
        "performance": "Quality",
        "thumbnail": "assets/style_thumbnails/signage.jpg"
    },
    "isometric_design": {
        "styles": [
            "Style: sai-isometric",
            "Style: sai-3d-model",
            "Style: sai-enhance"
        ],
        "positive": [
            "vibrant isometric style",
            "beautiful crisp intricate details",
            "clean 3D render"
        ],
        "negative": [
            "deformed",
            "mutated",
            "ugly",
            "disfigured",
            "blur",
            "realistic",
            "photographic"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "An isometric 3D design of",
        "thumbnail": "assets/style_thumbnails/isometric_design.jpg"
    },
    "papercraft_art": {
        "styles": [
            "Style: papercraft-papercut shadow box",
            "Style: sai-enhance"
        ],
        "positive": [
            "3D papercut shadow box",
            "layered dimensional depth",
            "handmade silhouette shadow",
            "high contrast papercut"
        ],
        "negative": [
            "painting",
            "drawing",
            "photo",
            "2D",
            "flat",
            "blurry",
            "noisy"
        ],
        "performance": "Quality",
        "aspect_ratio": "1024x1024",
        "prompt_prefix": "A beautiful papercraft artwork of",
        "thumbnail": "assets/style_thumbnails/papercraft_art.jpg"
    },
    "glitch_art": {
        "styles": [
            "Style: misc-glitch art",
            "Style: sai-enhance"
        ],
        "positive": [
            "breathtaking cinematic glitchy photo",
            "surreal dreamworld",
            "digital distortion",
            "award-winning"
        ],
        "negative": [
            "boring",
            "plain",
            "standard",
            "low resolution"
        ],
        "performance": "Quality",
        "aspect_ratio": "1152x896",
        "prompt_prefix": "A glitch art representation of",
        "thumbnail": "assets/style_thumbnails/glitch_art.jpg"
    },
    "analog_film": {
        "styles": [
            "Style: sai-analog film",
            "Style: sai-photographic"
        ],
        "positive": [
            "analog film photo",
            "faded film desaturated",
            "35mm photo grainy vignette vintage Kodachrome",
            "highly detailed found footage"
        ],
        "negative": [
            "painting",
            "drawing",
            "illustration",
            "glitch",
            "deformed",
            "mutated"
        ],
        "performance": "Quality",
        "aspect_ratio": "1152x896",
        "prompt_prefix": "An analog film photograph of",
        "thumbnail": "assets/style_thumbnails/analog_film.jpg"
    },
    "digital_painting": {
        "styles": [
            "Style: sai-digital art",
            "Style: sai-enhance"
        ],
        "positive": [
            "concept art digital artwork",
            "illustrative painterly",
            "matte painting highly detailed"
        ],
        "negative": [
            "photo",
            "photorealistic",
            "realism",
            "ugly"
        ],
        "performance": "Quality",
        "aspect_ratio": "1152x896",
        "prompt_prefix": "A beautiful digital painting of",
        "thumbnail": "assets/style_thumbnails/digital_painting.jpg"
    },
    "sai_3d_model": {
        "positive": [
            "professional 3d model {prompt}, octane render, highly detailed, volumetric, dramatic lighting"
        ],
        "negative": [
            "ugly, deformed, noisy, low poly, blurry, painting"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-3d-model.jpg",
        "original_name": "Style: sai-3d-model"
    },
    "sai_analog_film": {
        "positive": [
            "analog film photo {prompt}, faded film, desaturated, 35mm photo, grainy, vignette, vintage, Kodachrome, Lomography, stained, highly detailed, found footage"
        ],
        "negative": [
            "painting, drawing, illustration, glitch, deformed, mutated, cross-eyed, ugly, disfigured"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-analog_film.jpg",
        "original_name": "Style: sai-analog film"
    },
    "sai_anime": {
        "positive": [
            "anime artwork {prompt}, anime style, key visual, vibrant, studio anime,  highly detailed"
        ],
        "negative": [
            "photo, deformed, black and white, realism, disfigured, low contrast"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-anime.jpg",
        "original_name": "Style: sai-anime"
    },
    "sai_cinematic": {
        "positive": [
            "cinematic film still {prompt}, shallow depth of field, vignette, highly detailed, high budget Hollywood film, cinemascope, moody, epic, gorgeous"
        ],
        "negative": [
            "anime, cartoon, graphic, text, painting, crayon, graphite, abstract, glitch, blur, bokeh "
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-cinematic.jpg",
        "original_name": "Style: sai-cinematic"
    },
    "sai_comic_book": {
        "positive": [
            "comic {prompt}, graphic illustration, comic art, graphic novel art, vibrant, highly detailed"
        ],
        "negative": [
            "photograph, deformed, glitch, noisy, realistic, stock photo"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-comic_book.jpg",
        "original_name": "Style: sai-comic book"
    },
    "sai_craft_clay": {
        "positive": [
            "play-doh style {prompt}, sculpture, clay art, centered composition, Claymation"
        ],
        "negative": [
            "sloppy, messy, grainy, highly detailed, ultra textured, photo"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-craft_clay.jpg",
        "original_name": "Style: sai-craft clay"
    },
    "sai_digital_art": {
        "positive": [
            "concept art {prompt}, digital artwork, illustrative, painterly, matte painting, highly detailed"
        ],
        "negative": [
            "photo, photorealistic, realism, ugly"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-digital_art.jpg",
        "original_name": "Style: sai-digital art"
    },
    "sai_enhance": {
        "positive": [
            "breathtaking {prompt}, award-winning, professional, highly detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, distorted, grainy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-enhance.jpg",
        "original_name": "Style: sai-enhance"
    },
    "sai_fantasy_art": {
        "positive": [
            "ethereal fantasy concept art of  {prompt}, magnificent, celestial, ethereal, painterly, epic, majestic, magical, fantasy art, cover art, dreamy"
        ],
        "negative": [
            "photographic, realistic, realism, 35mm film, dslr, cropped, frame, text, deformed, glitch, noise, noisy, off-center, deformed, cross-eyed, closed eyes, bad anatomy, ugly, disfigured, sloppy, duplicate, mutated, black and white"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-fantasy_art.jpg",
        "original_name": "Style: sai-fantasy art"
    },
    "sai_isometric": {
        "positive": [
            "isometric style {prompt}, vibrant, beautiful, crisp, detailed, ultra detailed, intricate"
        ],
        "negative": [
            "deformed, mutated, ugly, disfigured, blur, blurry, noise, noisy, realistic, photographic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-isometric.jpg",
        "original_name": "Style: sai-isometric"
    },
    "sai_line_art": {
        "positive": [
            "line art drawing {prompt}, professional, sleek, modern, minimalist, graphic, line art, vector graphics"
        ],
        "negative": [
            "anime, photorealistic, 35mm film, deformed, glitch, blurry, noisy, off-center, deformed, cross-eyed, closed eyes, bad anatomy, ugly, disfigured, mutated, realism, realistic, impressionism, expressionism, oil, acrylic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-line_art.jpg",
        "original_name": "Style: sai-line art"
    },
    "sai_lowpoly": {
        "positive": [
            "low-poly style {prompt}, low-poly game art, polygon mesh, jagged, blocky, wireframe edges, centered composition"
        ],
        "negative": [
            "noisy, sloppy, messy, grainy, highly detailed, ultra textured, photo"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-lowpoly.jpg",
        "original_name": "Style: sai-lowpoly"
    },
    "sai_neonpunk": {
        "positive": [
            "neonpunk style {prompt}, cyberpunk, vaporwave, neon, vibes, vibrant, stunningly beautiful, crisp, detailed, sleek, ultramodern, magenta highlights, dark purple shadows, high contrast, cinematic, ultra detailed, intricate, professional"
        ],
        "negative": [
            "painting, drawing, illustration, glitch, deformed, mutated, cross-eyed, ugly, disfigured"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-neonpunk.jpg",
        "original_name": "Style: sai-neonpunk"
    },
    "sai_origami": {
        "positive": [
            "origami style {prompt}, paper art, pleated paper, folded, origami art, pleats, cut and fold, centered composition"
        ],
        "negative": [
            "noisy, sloppy, messy, grainy, highly detailed, ultra textured, photo"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-origami.jpg",
        "original_name": "Style: sai-origami"
    },
    "sai_photographic": {
        "positive": [
            "cinematic photo {prompt}, 35mm photograph, film, bokeh, professional, 4k, highly detailed"
        ],
        "negative": [
            "drawing, painting, crayon, sketch, graphite, impressionist, noisy, blurry, soft, deformed, ugly"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-photographic.jpg",
        "original_name": "Style: sai-photographic"
    },
    "sai_pixel_art": {
        "positive": [
            "pixel-art {prompt}, low-res, blocky, pixel art style, 8-bit graphics"
        ],
        "negative": [
            "sloppy, messy, blurry, noisy, highly detailed, ultra textured, photo, realistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-pixel_art.jpg",
        "original_name": "Style: sai-pixel art"
    },
    "sai_texture": {
        "positive": [
            "texture {prompt} top down close-up"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry"
        ],
        "thumbnail": "assets/style_thumbnails/Style__sai-texture.jpg",
        "original_name": "Style: sai-texture"
    },
    "ads_advertising": {
        "positive": [
            "Advertising poster style {prompt}, Professional, modern, product-focused, commercial, eye-catching, highly detailed"
        ],
        "negative": [
            "noisy, blurry, amateurish, sloppy, unattractive"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-advertising.jpg",
        "original_name": "Style: ads-advertising"
    },
    "ads_automotive": {
        "positive": [
            "Automotive advertisement style {prompt}, Sleek, dynamic, professional, commercial, vehicle-focused, high-resolution, highly detailed"
        ],
        "negative": [
            "noisy, blurry, unattractive, sloppy, unprofessional"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-automotive.jpg",
        "original_name": "Style: ads-automotive"
    },
    "ads_corporate": {
        "positive": [
            "Corporate branding style {prompt}, Professional, clean, modern, sleek, minimalist, business-oriented, highly detailed"
        ],
        "negative": [
            "noisy, blurry, grungy, sloppy, cluttered, disorganized"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-corporate.jpg",
        "original_name": "Style: ads-corporate"
    },
    "ads_fashion_editorial": {
        "positive": [
            "Fashion editorial style {prompt}, High fashion, trendy, stylish, editorial, magazine style, professional, highly detailed"
        ],
        "negative": [
            "outdated, blurry, noisy, unattractive, sloppy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-fashion_editorial.jpg",
        "original_name": "Style: ads-fashion editorial"
    },
    "ads_food_photography": {
        "positive": [
            "Food photography style {prompt}, Appetizing, professional, culinary, high-resolution, commercial, highly detailed"
        ],
        "negative": [
            "unappetizing, sloppy, unprofessional, noisy, blurry"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-food_photography.jpg",
        "original_name": "Style: ads-food photography"
    },
    "ads_luxury": {
        "positive": [
            "Luxury product style {prompt}, Elegant, sophisticated, high-end, luxurious, professional, highly detailed"
        ],
        "negative": [
            "cheap, noisy, blurry, unattractive, amateurish"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-luxury.jpg",
        "original_name": "Style: ads-luxury"
    },
    "ads_real_estate": {
        "positive": [
            "Real estate photography style {prompt}, Professional, inviting, well-lit, high-resolution, property-focused, commercial, highly detailed"
        ],
        "negative": [
            "dark, blurry, unappealing, noisy, unprofessional"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-real_estate.jpg",
        "original_name": "Style: ads-real estate"
    },
    "ads_retail": {
        "positive": [
            "Retail packaging style {prompt}, Vibrant, enticing, commercial, product-focused, eye-catching, professional, highly detailed"
        ],
        "negative": [
            "noisy, blurry, amateurish, sloppy, unattractive"
        ],
        "thumbnail": "assets/style_thumbnails/Style__ads-retail.jpg",
        "original_name": "Style: ads-retail"
    },
    "artstyle_abstract": {
        "positive": [
            "abstract style {prompt}, non-representational, colors and shapes, expression of feelings, imaginative, highly detailed"
        ],
        "negative": [
            "realistic, photographic, figurative, concrete"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-abstract.jpg",
        "original_name": "Style: artstyle-abstract"
    },
    "artstyle_abstract_expressionism": {
        "positive": [
            "abstract expressionist painting {prompt}, energetic brushwork, bold colors, abstract forms, expressive, emotional"
        ],
        "negative": [
            "realistic, photorealistic, low contrast, plain, simple, monochrome"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-abstract_expressionism.jpg",
        "original_name": "Style: artstyle-abstract expressionism"
    },
    "artstyle_art_deco": {
        "positive": [
            "Art Deco style {prompt}, geometric shapes, bold colors, luxurious, elegant, decorative, symmetrical, ornate, detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, modernist, minimalist"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-art_deco.jpg",
        "original_name": "Style: artstyle-art deco"
    },
    "artstyle_art_nouveau": {
        "positive": [
            "Art Nouveau style {prompt}, elegant, decorative, curvilinear forms, nature-inspired, ornate, detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, modernist, minimalist"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-art_nouveau.jpg",
        "original_name": "Style: artstyle-art nouveau"
    },
    "artstyle_constructivist": {
        "positive": [
            "constructivist style {prompt}, geometric shapes, bold colors, dynamic composition, propaganda art style"
        ],
        "negative": [
            "realistic, photorealistic, low contrast, plain, simple, abstract expressionism"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-constructivist.jpg",
        "original_name": "Style: artstyle-constructivist"
    },
    "artstyle_cubist": {
        "positive": [
            "cubist artwork {prompt}, geometric shapes, abstract, innovative, revolutionary"
        ],
        "negative": [
            "anime, photorealistic, 35mm film, deformed, glitch, low contrast, noisy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-cubist.jpg",
        "original_name": "Style: artstyle-cubist"
    },
    "artstyle_expressionist": {
        "positive": [
            "expressionist {prompt}, raw, emotional, dynamic, distortion for emotional effect, vibrant, use of unusual colors, detailed"
        ],
        "negative": [
            "realism, symmetry, quiet, calm, photo"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-expressionist.jpg",
        "original_name": "Style: artstyle-expressionist"
    },
    "artstyle_graffiti": {
        "positive": [
            "graffiti style {prompt}, street art, vibrant, urban, detailed, tag, mural"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-graffiti.jpg",
        "original_name": "Style: artstyle-graffiti"
    },
    "artstyle_hyperrealism": {
        "positive": [
            "hyperrealistic art {prompt}, extremely high-resolution details, photographic, realism pushed to extreme, fine texture, incredibly lifelike"
        ],
        "negative": [
            "simplified, abstract, unrealistic, impressionistic, low resolution"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-hyperrealism.jpg",
        "original_name": "Style: artstyle-hyperrealism"
    },
    "artstyle_impressionist": {
        "positive": [
            "impressionist painting {prompt}, loose brushwork, vibrant color, light and shadow play, captures feeling over form"
        ],
        "negative": [
            "anime, photorealistic, 35mm film, deformed, glitch, low contrast, noisy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-impressionist.jpg",
        "original_name": "Style: artstyle-impressionist"
    },
    "artstyle_pixar": {
        "positive": [
            "pixar style render, caricature, {prompt},  looking at viewer, flat colors, 4k, professional, award-winning, highly detailed, volumetric, dramatic lighting"
        ],
        "negative": [
            "low poly, painting, realistic, photo, line drawing"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-pixar.jpg",
        "original_name": "Style: artstyle-pixar"
    },
    "artstyle_pointillism": {
        "positive": [
            "pointillism style {prompt}, composed entirely of small, distinct dots of color, vibrant, highly detailed"
        ],
        "negative": [
            "line drawing, smooth shading, large color fields, simplistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-pointillism.jpg",
        "original_name": "Style: artstyle-pointillism"
    },
    "artstyle_pop_art": {
        "positive": [
            "Pop Art style {prompt}, bright colors, bold outlines, popular culture themes, ironic or kitsch"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, minimalist"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-pop_art.jpg",
        "original_name": "Style: artstyle-pop art"
    },
    "artstyle_psychedelic": {
        "positive": [
            "psychedelic style {prompt}, vibrant colors, swirling patterns, abstract forms, surreal, trippy"
        ],
        "negative": [
            "monochrome, black and white, low contrast, realistic, photorealistic, plain, simple"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-psychedelic.jpg",
        "original_name": "Style: artstyle-psychedelic"
    },
    "artstyle_renaissance": {
        "positive": [
            "Renaissance style {prompt}, realistic, perspective, light and shadow, religious or mythological themes, highly detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, modernist, minimalist, abstract"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-renaissance.jpg",
        "original_name": "Style: artstyle-renaissance"
    },
    "artstyle_steampunk": {
        "positive": [
            "steampunk style {prompt}, antique, mechanical, brass and copper tones, gears, intricate, detailed"
        ],
        "negative": [
            "deformed, glitch, noisy, low contrast, anime, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-steampunk.jpg",
        "original_name": "Style: artstyle-steampunk"
    },
    "artstyle_surrealist": {
        "positive": [
            "surrealist art {prompt}, dreamlike, mysterious, provocative, symbolic, intricate, detailed"
        ],
        "negative": [
            "anime, photorealistic, realistic, deformed, glitch, noisy, low contrast"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-surrealist.jpg",
        "original_name": "Style: artstyle-surrealist"
    },
    "artstyle_typography": {
        "positive": [
            "typographic art {prompt}, stylized, intricate, detailed, artistic, text-based"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-typography.jpg",
        "original_name": "Style: artstyle-typography"
    },
    "artstyle_watercolor": {
        "positive": [
            "watercolor painting {prompt}, vibrant, beautiful, painterly, detailed, textural, artistic"
        ],
        "negative": [
            "anime, photorealistic, 35mm film, deformed, glitch, low contrast, noisy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__artstyle-watercolor.jpg",
        "original_name": "Style: artstyle-watercolor"
    },
    "futuristic_biomechanical": {
        "positive": [
            "biomechanical style {prompt}, blend of organic and mechanical elements, futuristic, cybernetic, detailed, intricate"
        ],
        "negative": [
            "natural, rustic, primitive, organic, simplistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-biomechanical.jpg",
        "original_name": "Style: futuristic-biomechanical"
    },
    "futuristic_biomechanical_cyberpunk": {
        "positive": [
            "biomechanical cyberpunk {prompt}, cybernetics, human-machine fusion, dystopian, organic meets artificial, dark, intricate, highly detailed"
        ],
        "negative": [
            "natural, colorful, deformed, sketch, low contrast, watercolor"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-biomechanical_cyberpunk.jpg",
        "original_name": "Style: futuristic-biomechanical cyberpunk"
    },
    "futuristic_cybernetic": {
        "positive": [
            "cybernetic style {prompt}, futuristic, technological, cybernetic enhancements, robotics, artificial intelligence themes"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, historical, medieval"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-cybernetic.jpg",
        "original_name": "Style: futuristic-cybernetic"
    },
    "futuristic_cybernetic_robot": {
        "positive": [
            "cybernetic robot {prompt}, android, AI, machine, metal, wires, tech, futuristic, highly detailed"
        ],
        "negative": [
            "organic, natural, human, sketch, watercolor, low contrast"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-cybernetic_robot.jpg",
        "original_name": "Style: futuristic-cybernetic robot"
    },
    "futuristic_cyberpunk_cityscape": {
        "positive": [
            "cyberpunk cityscape {prompt}, neon lights, dark alleys, skyscrapers, futuristic, vibrant colors, high contrast, highly detailed"
        ],
        "negative": [
            "natural, rural, deformed, low contrast, black and white, sketch, watercolor"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-cyberpunk_cityscape.jpg",
        "original_name": "Style: futuristic-cyberpunk cityscape"
    },
    "futuristic_futuristic": {
        "positive": [
            "futuristic style {prompt}, sleek, modern, ultramodern, high tech, detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, vintage, antique"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-futuristic.jpg",
        "original_name": "Style: futuristic-futuristic"
    },
    "futuristic_retro_cyberpunk": {
        "positive": [
            "retro cyberpunk {prompt}, 80's inspired, synthwave, neon, vibrant, detailed, retro futurism"
        ],
        "negative": [
            "modern, desaturated, black and white, realism, low contrast"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-retro_cyberpunk.jpg",
        "original_name": "Style: futuristic-retro cyberpunk"
    },
    "futuristic_retro_futurism": {
        "positive": [
            "retro-futuristic {prompt}, vintage sci-fi, 50s and 60s style, atomic age, vibrant, highly detailed"
        ],
        "negative": [
            "contemporary, realistic, rustic, primitive"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-retro_futurism.jpg",
        "original_name": "Style: futuristic-retro futurism"
    },
    "futuristic_sci_fi": {
        "positive": [
            "sci-fi style {prompt}, futuristic, technological, alien worlds, space themes, advanced civilizations"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, historical, medieval"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-sci-fi.jpg",
        "original_name": "Style: futuristic-sci-fi"
    },
    "futuristic_vaporwave": {
        "positive": [
            "vaporwave style {prompt}, retro aesthetic, cyberpunk, vibrant, neon colors, vintage 80s and 90s style, highly detailed"
        ],
        "negative": [
            "monochrome, muted colors, realism, rustic, minimalist, dark"
        ],
        "thumbnail": "assets/style_thumbnails/Style__futuristic-vaporwave.jpg",
        "original_name": "Style: futuristic-vaporwave"
    },
    "game_bubble_bobble": {
        "positive": [
            "Bubble Bobble style {prompt}, 8-bit, cute, pixelated, fantasy, vibrant, reminiscent of Bubble Bobble game"
        ],
        "negative": [
            "realistic, modern, photorealistic, violent, horror"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-bubble_bobble.jpg",
        "original_name": "Style: game-bubble bobble"
    },
    "game_cyberpunk_game": {
        "positive": [
            "cyberpunk game style {prompt}, neon, dystopian, futuristic, digital, vibrant, detailed, high contrast, reminiscent of cyberpunk genre video games"
        ],
        "negative": [
            "historical, natural, rustic, low detailed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-cyberpunk_game.jpg",
        "original_name": "Style: game-cyberpunk game"
    },
    "game_fighting_game": {
        "positive": [
            "fighting game style {prompt}, dynamic, vibrant, action-packed, detailed character design, reminiscent of fighting video games"
        ],
        "negative": [
            "peaceful, calm, minimalist, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-fighting_game.jpg",
        "original_name": "Style: game-fighting game"
    },
    "game_fortnite": {
        "positive": [
            "fortnite style, character artwork, {prompt}, dynamic, vibrant, detailed character, reminiscent of fortnite"
        ],
        "negative": [
            "minimalist, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-fortnite.jpg",
        "original_name": "Style: game-fortnite"
    },
    "game_gta": {
        "positive": [
            "GTA-style artwork {prompt}, satirical, exaggerated, pop art style, vibrant colors, iconic characters, action-packed"
        ],
        "negative": [
            "realistic, black and white, low contrast, impressionist, cubist, noisy, blurry, deformed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-gta.jpg",
        "original_name": "Style: game-gta"
    },
    "game_mario": {
        "positive": [
            "Super Mario style {prompt}, vibrant, cute, cartoony, fantasy, playful, reminiscent of Super Mario series"
        ],
        "negative": [
            "realistic, modern, horror, dystopian, violent"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-mario.jpg",
        "original_name": "Style: game-mario"
    },
    "game_minecraft": {
        "positive": [
            "Minecraft style {prompt}, blocky, pixelated, vibrant colors, recognizable characters and objects, game assets"
        ],
        "negative": [
            "smooth, realistic, detailed, photorealistic, noise, blurry, deformed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-minecraft.jpg",
        "original_name": "Style: game-minecraft"
    },
    "game_pokemon": {
        "positive": [
            "Pok\u00e9mon style {prompt}, vibrant, cute, anime, fantasy, reminiscent of Pok\u00e9mon series"
        ],
        "negative": [
            "realistic, modern, horror, dystopian, violent"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-pokemon.jpg",
        "original_name": "Style: game-pokemon"
    },
    "game_retro_arcade": {
        "positive": [
            "retro arcade style {prompt}, 8-bit, pixelated, vibrant, classic video game, old school gaming, reminiscent of 80s and 90s arcade games"
        ],
        "negative": [
            "modern, ultra-high resolution, photorealistic, 3D"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-retro_arcade.jpg",
        "original_name": "Style: game-retro arcade"
    },
    "game_retro_game": {
        "positive": [
            "retro game art {prompt}, 16-bit, vibrant colors, pixelated, nostalgic, charming, fun"
        ],
        "negative": [
            "realistic, photorealistic, 35mm film, deformed, glitch, low contrast, noisy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-retro_game.jpg",
        "original_name": "Style: game-retro game"
    },
    "game_rpg_fantasy_game": {
        "positive": [
            "role-playing game (RPG) style fantasy {prompt}, detailed, vibrant, immersive, reminiscent of high fantasy RPG games"
        ],
        "negative": [
            "sci-fi, modern, urban, futuristic, low detailed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-rpg_fantasy_game.jpg",
        "original_name": "Style: game-rpg fantasy game"
    },
    "game_strategy_game": {
        "positive": [
            "strategy game style {prompt}, overhead view, detailed map, units, reminiscent of real-time strategy video games"
        ],
        "negative": [
            "first-person view, modern, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-strategy_game.jpg",
        "original_name": "Style: game-strategy game"
    },
    "game_streetfighter": {
        "positive": [
            "Street Fighter style {prompt}, vibrant, dynamic, arcade, 2D fighting game, highly detailed, reminiscent of Street Fighter series"
        ],
        "negative": [
            "3D, realistic, modern, photorealistic, turn-based strategy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-streetfighter.jpg",
        "original_name": "Style: game-streetfighter"
    },
    "game_world_of_warcraft": {
        "positive": [
            " World of Warcraft style , screenshot, {prompt}, vibrant, dynamic, pc ingame graphics , screenshot, highly detailed, reminiscent of World of Warcraft"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Style__game-world_of_warcraft.jpg",
        "original_name": "Style: game-world of warcraft"
    },
    "game_zelda": {
        "positive": [
            "Legend of Zelda style {prompt}, vibrant, fantasy, detailed, epic, heroic, reminiscent of The Legend of Zelda series"
        ],
        "negative": [
            "sci-fi, modern, realistic, horror"
        ],
        "thumbnail": "assets/style_thumbnails/Style__game-zelda.jpg",
        "original_name": "Style: game-zelda"
    },
    "misc_3d_caricature": {
        "positive": [
            "disney 3d cartoon style, caricature, {prompt}, highly detailed, vfx"
        ],
        "negative": [
            "black and white"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-3D-Caricature.jpg",
        "original_name": "Style: misc-3D-Caricature"
    },
    "misc_architectural": {
        "positive": [
            "architectural style {prompt}, clean lines, geometric shapes, minimalist, modern, architectural drawing, highly detailed"
        ],
        "negative": [
            "curved lines, ornate, baroque, abstract, grunge"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-architectural.jpg",
        "original_name": "Style: misc-architectural"
    },
    "misc_character_referencesheet": {
        "positive": [
            "character reference sheet {prompt}, turnaround views, detailed anatomy, color palette, multiple poses, highly detailed"
        ],
        "negative": [
            "simplistic, minimalist, vague, incomplete"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-character_referencesheet.jpg",
        "original_name": "Style: misc-character referencesheet"
    },
    "misc_chibi": {
        "positive": [
            "chibi style {prompt}, cute, adorable, bright colors, cheerful, highly detailed"
        ],
        "negative": [
            "dark, scary, realistic, monochrome, abstract"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-chibi.jpg",
        "original_name": "Style: misc-chibi"
    },
    "misc_dieselpunk": {
        "positive": [
            "dieselpunk style {prompt}, retro-futuristic, gritty, 1920s-1950s, sci-fi, highly detailed"
        ],
        "negative": [
            "clean, crisp, digital"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-dieselpunk.jpg",
        "original_name": "Style: misc-dieselpunk"
    },
    "misc_disco": {
        "positive": [
            "disco-themed {prompt}, vibrant, groovy, retro 70s style, shiny disco balls, neon lights, dance floor, highly detailed"
        ],
        "negative": [
            "minimalist, rustic, monochrome, contemporary, simplistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-disco.jpg",
        "original_name": "Style: misc-disco"
    },
    "misc_dreamscape": {
        "positive": [
            "dreamscape {prompt}, surreal, ethereal, dreamy, mysterious, fantasy, highly detailed"
        ],
        "negative": [
            "realistic, concrete, ordinary, mundane"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-dreamscape.jpg",
        "original_name": "Style: misc-dreamscape"
    },
    "misc_dystopian": {
        "positive": [
            "dystopian style {prompt}, bleak, post-apocalyptic, somber, dramatic, highly detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, cheerful, optimistic, vibrant, colorful"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-dystopian.jpg",
        "original_name": "Style: misc-dystopian"
    },
    "misc_fairy_tale": {
        "positive": [
            "fairy tale {prompt}, magical, fantastical, enchanting, storybook style, highly detailed"
        ],
        "negative": [
            "realistic, modern, ordinary, mundane"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-fairy_tale.jpg",
        "original_name": "Style: misc-fairy tale"
    },
    "misc_funkopop": {
        "positive": [
            "funkopop style, {prompt}, bright colors, highly detailed"
        ],
        "negative": [
            "dark, scary, realistic, monochrome, abstract"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-funkopop.jpg",
        "original_name": "Style: misc-funkopop"
    },
    "misc_glitch_art": {
        "positive": [
            "breathtaking cinematic glitchy photo, surreal dreamworld, {prompt} ,digital distortion, highly detailed, award-winning"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Style__misc-glitch_art.jpg",
        "original_name": "Style: misc-glitch art"
    },
    "misc_gothic": {
        "positive": [
            "gothic style {prompt}, dark, mysterious, haunting, dramatic, ornate, detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, cheerful, optimistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-gothic.jpg",
        "original_name": "Style: misc-gothic"
    },
    "misc_grunge": {
        "positive": [
            "grunge style {prompt}, textured, distressed, vintage, edgy, punk rock vibe, dirty, noisy"
        ],
        "negative": [
            "smooth, clean, minimalist, sleek, modern, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-grunge.jpg",
        "original_name": "Style: misc-grunge"
    },
    "misc_horror": {
        "positive": [
            "horror-themed {prompt}, eerie, unsettling, dark, spooky, suspenseful, grim, highly detailed"
        ],
        "negative": [
            "cheerful, bright, vibrant, light-hearted, cute"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-horror.jpg",
        "original_name": "Style: misc-horror"
    },
    "misc_kawaii": {
        "positive": [
            "kawaii style {prompt}, cute, adorable, brightly colored, cheerful, anime influence, highly detailed"
        ],
        "negative": [
            "dark, scary, realistic, monochrome, abstract"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-kawaii.jpg",
        "original_name": "Style: misc-kawaii"
    },
    "misc_lovecraftian": {
        "positive": [
            "lovecraftian horror {prompt}, eldritch, cosmic horror, unknown, mysterious, surreal, highly detailed"
        ],
        "negative": [
            "light-hearted, mundane, familiar, simplistic, realistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-lovecraftian.jpg",
        "original_name": "Style: misc-lovecraftian"
    },
    "misc_macabre": {
        "positive": [
            "macabre style {prompt}, dark, gothic, grim, haunting, highly detailed"
        ],
        "negative": [
            "bright, cheerful, light-hearted, cartoonish, cute"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-macabre.jpg",
        "original_name": "Style: misc-macabre"
    },
    "misc_magic_the_gathering": {
        "positive": [
            "Magic the gathering style,  {prompt}, magnificent, celestial, ethereal, painterly, epic, majestic, magical, fantasy art, card art, dreamy"
        ],
        "negative": [
            "photographic, realistic, realism, 35mm film, dslr, cropped, deformed, glitch, noise, noisy, off-center, duplicate, mutated, black and white"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-magic_the_gathering.jpg",
        "original_name": "Style: misc-magic the gathering"
    },
    "misc_manga": {
        "positive": [
            "manga style {prompt}, vibrant, high-energy, detailed, iconic, Japanese comic style"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, Western comic style"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-manga.jpg",
        "original_name": "Style: misc-manga"
    },
    "misc_metropolis": {
        "positive": [
            "metropolis-themed {prompt}, urban, cityscape, skyscrapers, modern, futuristic, highly detailed"
        ],
        "negative": [
            "rural, natural, rustic, historical, simple"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-metropolis.jpg",
        "original_name": "Style: misc-metropolis"
    },
    "misc_minimalist": {
        "positive": [
            "minimalist style {prompt}, simple, clean, uncluttered, modern, elegant"
        ],
        "negative": [
            "ornate, complicated, highly detailed, cluttered, disordered, messy, noisy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-minimalist.jpg",
        "original_name": "Style: misc-minimalist"
    },
    "misc_monochrome": {
        "positive": [
            "monochrome {prompt}, black and white, contrast, tone, texture, detailed"
        ],
        "negative": [
            "colorful, vibrant, noisy, blurry, deformed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-monochrome.jpg",
        "original_name": "Style: misc-monochrome"
    },
    "misc_nautical": {
        "positive": [
            "nautical-themed {prompt}, sea, ocean, ships, maritime, beach, marine life, highly detailed"
        ],
        "negative": [
            "landlocked, desert, mountains, urban, rustic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-nautical.jpg",
        "original_name": "Style: misc-nautical"
    },
    "misc_scientific": {
        "positive": [
            "scientific illustration, {prompt}, detailed, annotated, educational, informational"
        ],
        "negative": [
            "simplistic, cartoon, abstract"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-scientific.jpg",
        "original_name": "Style: misc-scientific"
    },
    "misc_silhouette": {
        "positive": [
            "silhouette style concept art {prompt} digital artwork, illustrative, painterly, matte painting, highly detailed, high contrast, stark, dramatic"
        ],
        "negative": [
            " photo, photorealistic,realism"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-silhouette.jpg",
        "original_name": "Style: misc-silhouette"
    },
    "misc_space": {
        "positive": [
            "space-themed {prompt}, cosmic, celestial, stars, galaxies, nebulas, planets, science fiction, highly detailed"
        ],
        "negative": [
            "earthly, mundane, ground-based, realism"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-space.jpg",
        "original_name": "Style: misc-space"
    },
    "misc_stained_glass": {
        "positive": [
            "stained glass style {prompt}, vibrant, beautiful, translucent, intricate, detailed"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-stained_glass.jpg",
        "original_name": "Style: misc-stained glass"
    },
    "misc_techwear_fashion": {
        "positive": [
            "techwear fashion {prompt}, futuristic, cyberpunk, urban, tactical, sleek, dark, highly detailed"
        ],
        "negative": [
            "vintage, rural, colorful, low contrast, realism, sketch, watercolor"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-techwear_fashion.jpg",
        "original_name": "Style: misc-techwear fashion"
    },
    "misc_tribal": {
        "positive": [
            "tribal style {prompt}, indigenous, ethnic, traditional patterns, bold, natural colors, highly detailed"
        ],
        "negative": [
            "modern, futuristic, minimalist, pastel"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-tribal.jpg",
        "original_name": "Style: misc-tribal"
    },
    "misc_zentangle": {
        "positive": [
            "zentangle {prompt}, intricate, abstract, monochrome, patterns, meditative, highly detailed"
        ],
        "negative": [
            "colorful, representative, simplistic, large fields of color"
        ],
        "thumbnail": "assets/style_thumbnails/Style__misc-zentangle.jpg",
        "original_name": "Style: misc-zentangle"
    },
    "papercraft_collage": {
        "positive": [
            "collage style {prompt}, mixed media, layered, textural, detailed, artistic"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-collage.jpg",
        "original_name": "Style: papercraft-collage"
    },
    "papercraft_flat_papercut": {
        "positive": [
            "flat papercut style {prompt}, silhouette, clean cuts, paper, sharp edges, minimalist, color block"
        ],
        "negative": [
            "3D, high detail, noise, grainy, blurry, painting, drawing, photo, disfigured"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-flat_papercut.jpg",
        "original_name": "Style: papercraft-flat papercut"
    },
    "papercraft_kirigami": {
        "positive": [
            "kirigami representation of {prompt}, 3D, paper folding, paper cutting, Japanese, intricate, symmetrical, precision, clean lines"
        ],
        "negative": [
            "painting, drawing, 2D, noisy, blurry, deformed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-kirigami.jpg",
        "original_name": "Style: papercraft-kirigami"
    },
    "papercraft_paper_mache": {
        "positive": [
            "paper mache representation of {prompt}, 3D, sculptural, textured, handmade, vibrant, fun"
        ],
        "negative": [
            "2D, flat, photo, sketch, digital art, deformed, noisy, blurry"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-paper_mache.jpg",
        "original_name": "Style: papercraft-paper mache"
    },
    "papercraft_paper_quilling": {
        "positive": [
            "paper quilling art of {prompt}, intricate, delicate, curling, rolling, shaping, coiling, loops, 3D, dimensional, ornamental"
        ],
        "negative": [
            "photo, painting, drawing, 2D, flat, deformed, noisy, blurry"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-paper_quilling.jpg",
        "original_name": "Style: papercraft-paper quilling"
    },
    "papercraft_papercut_collage": {
        "positive": [
            "papercut collage of {prompt}, mixed media, textured paper, overlapping, asymmetrical, abstract, vibrant"
        ],
        "negative": [
            "photo, 3D, realistic, drawing, painting, high detail, disfigured"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-papercut_collage.jpg",
        "original_name": "Style: papercraft-papercut collage"
    },
    "papercraft_papercut_shadow_box": {
        "positive": [
            "3D papercut shadow box of {prompt}, layered, dimensional, depth, silhouette, shadow, papercut, handmade, high contrast"
        ],
        "negative": [
            "painting, drawing, photo, 2D, flat, high detail, blurry, noisy, disfigured"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-papercut_shadow_box.jpg",
        "original_name": "Style: papercraft-papercut shadow box"
    },
    "papercraft_stacked_papercut": {
        "positive": [
            "stacked papercut art of {prompt}, 3D, layered, dimensional, depth, precision cut, stacked layers, papercut, high contrast"
        ],
        "negative": [
            "2D, flat, noisy, blurry, painting, drawing, photo, deformed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-stacked_papercut.jpg",
        "original_name": "Style: papercraft-stacked papercut"
    },
    "papercraft_thick_layered_papercut": {
        "positive": [
            "thick layered papercut art of {prompt}, deep 3D, volumetric, dimensional, depth, thick paper, high stack, heavy texture, tangible layers"
        ],
        "negative": [
            "2D, flat, thin paper, low stack, smooth texture, painting, drawing, photo, deformed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__papercraft-thick_layered_papercut.jpg",
        "original_name": "Style: papercraft-thick layered papercut"
    },
    "photo_alien": {
        "positive": [
            "alien-themed {prompt}, extraterrestrial, cosmic, otherworldly, mysterious, sci-fi, highly detailed"
        ],
        "negative": [
            "earthly, mundane, common, realistic, simple"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-alien.jpg",
        "original_name": "Style: photo-alien"
    },
    "photo_film_noir": {
        "positive": [
            "film noir style {prompt}, monochrome, high contrast, dramatic shadows, 1940s style, mysterious, cinematic"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, realism, photorealistic, vibrant, colorful"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-film_noir.jpg",
        "original_name": "Style: photo-film noir"
    },
    "photo_found_footage_polaroid": {
        "positive": [
            "a grainy real polaroid photo, {prompt}, flash photography, dimly lit, bad lighting, dark background, bright camera flash, creepy, nostalgic, night time, moody ambience, film grain"
        ],
        "negative": [
            "illegible text, blurry text, unreadable text, colourful, unrealistic, professional photography, professional lighting, day time, bright, oversaturated, high contrast, high quality, 3d render, painting, art"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-found-footage-polaroid.jpg",
        "original_name": "Style: photo-found-footage-polaroid"
    },
    "photo_hdr": {
        "positive": [
            "HDR photo of {prompt}, High dynamic range, vivid, rich details, clear shadows and highlights, realistic, intense, enhanced contrast, highly detailed"
        ],
        "negative": [
            "flat, low contrast, oversaturated, underexposed, overexposed, blurred, noisy"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-hdr.jpg",
        "original_name": "Style: photo-hdr"
    },
    "photo_long_exposure": {
        "positive": [
            "long exposure photo of {prompt}, Blurred motion, streaks of light, surreal, dreamy, ghosting effect, highly detailed"
        ],
        "negative": [
            "static, noisy, deformed, shaky, abrupt, flat, low contrast"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-long_exposure.jpg",
        "original_name": "Style: photo-long exposure"
    },
    "photo_neon_noir": {
        "positive": [
            "neon noir {prompt}, cyberpunk, dark, rainy streets, neon signs, high contrast, low light, vibrant, highly detailed"
        ],
        "negative": [
            "bright, sunny, daytime, low contrast, black and white, sketch, watercolor"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-neon_noir.jpg",
        "original_name": "Style: photo-neon noir"
    },
    "photo_silhouette": {
        "positive": [
            "silhouette style {prompt}, high contrast, minimalistic, black and white, stark, dramatic"
        ],
        "negative": [
            "ugly, deformed, noisy, blurry, low contrast, color, realism, photorealistic"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-silhouette.jpg",
        "original_name": "Style: photo-silhouette"
    },
    "photo_tilt_shift": {
        "positive": [
            "tilt-shift photo of {prompt}, Selective focus, miniature effect, blurred background, highly detailed, vibrant, perspective control"
        ],
        "negative": [
            "blurry, noisy, deformed, flat, low contrast, unrealistic, oversaturated, underexposed"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-tilt-shift.jpg",
        "original_name": "Style: photo-tilt-shift"
    },
    "photo_red_camera": {
        "positive": [
            "cinematic scene from {prompt}, American Shot, captured by Red Camera with 85mm lens, film directed by Wes Anderson, melancholic, environmental lighting"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Style__photo-red-camera.jpg",
        "original_name": "Style: photo-red-camera"
    },
    "photo_duotone": {
        "positive": [
            "duotone photo, {prompt}, high contrast, two color tones only, highly detailed"
        ],
        "negative": [
            "full color, complex palette"
        ],
        "thumbnail": "assets/style_thumbnails/Style__photo-duotone.jpg",
        "original_name": "Style: photo-duotone"
    },
    "all": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__all.jpg",
        "original_name": "Artify: all"
    },
    "popular": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__popular.jpg",
        "original_name": "Artify: popular"
    },
    "greg_mode": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__greg_mode.jpg",
        "original_name": "Artify: greg mode"
    },
    "3d": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__3D.jpg",
        "original_name": "Artify: 3D"
    },
    "abstract": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__abstract.jpg",
        "original_name": "Artify: abstract"
    },
    "angular": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__angular.jpg",
        "original_name": "Artify: angular"
    },
    "anime": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__anime.jpg",
        "original_name": "Artify: anime"
    },
    "architecture": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__architecture.jpg",
        "original_name": "Artify: architecture"
    },
    "art_nouveau": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__art_nouveau.jpg",
        "original_name": "Artify: art nouveau"
    },
    "art_deco": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__art_deco.jpg",
        "original_name": "Artify: art deco"
    },
    "baroque": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__baroque.jpg",
        "original_name": "Artify: baroque"
    },
    "bauhaus": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__bauhaus.jpg",
        "original_name": "Artify: bauhaus"
    },
    "cartoon": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__cartoon.jpg",
        "original_name": "Artify: cartoon"
    },
    "character": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__character.jpg",
        "original_name": "Artify: character"
    },
    "childrens_illustration": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__children's_illustration.jpg",
        "original_name": "Artify: children's illustration"
    },
    "cityscape": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__cityscape.jpg",
        "original_name": "Artify: cityscape"
    },
    "clean": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__clean.jpg",
        "original_name": "Artify: clean"
    },
    "cloudscape": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__cloudscape.jpg",
        "original_name": "Artify: cloudscape"
    },
    "collage": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__collage.jpg",
        "original_name": "Artify: collage"
    },
    "colorful": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__colorful.jpg",
        "original_name": "Artify: colorful"
    },
    "comics": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__comics.jpg",
        "original_name": "Artify: comics"
    },
    "cubism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__cubism.jpg",
        "original_name": "Artify: cubism"
    },
    "dark": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__dark.jpg",
        "original_name": "Artify: dark"
    },
    "detailed": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__detailed.jpg",
        "original_name": "Artify: detailed"
    },
    "digital": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__digital.jpg",
        "original_name": "Artify: digital"
    },
    "expressionism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__expressionism.jpg",
        "original_name": "Artify: expressionism"
    },
    "fantasy": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__fantasy.jpg",
        "original_name": "Artify: fantasy"
    },
    "fashion": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__fashion.jpg",
        "original_name": "Artify: fashion"
    },
    "fauvism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__fauvism.jpg",
        "original_name": "Artify: fauvism"
    },
    "figurativism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__figurativism.jpg",
        "original_name": "Artify: figurativism"
    },
    "gore": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__gore.jpg",
        "original_name": "Artify: gore"
    },
    "graffiti": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__graffiti.jpg",
        "original_name": "Artify: graffiti"
    },
    "graphic_design": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__graphic_design.jpg",
        "original_name": "Artify: graphic design"
    },
    "high_contrast": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__high_contrast.jpg",
        "original_name": "Artify: high contrast"
    },
    "horror": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__horror.jpg",
        "original_name": "Artify: horror"
    },
    "impressionism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__impressionism.jpg",
        "original_name": "Artify: impressionism"
    },
    "installation": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__installation.jpg",
        "original_name": "Artify: installation"
    },
    "landscape": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__landscape.jpg",
        "original_name": "Artify: landscape"
    },
    "light": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__light.jpg",
        "original_name": "Artify: light"
    },
    "line_drawing": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__line_drawing.jpg",
        "original_name": "Artify: line drawing"
    },
    "low_contrast": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__low_contrast.jpg",
        "original_name": "Artify: low contrast"
    },
    "luminism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__luminism.jpg",
        "original_name": "Artify: luminism"
    },
    "magical_realism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__magical_realism.jpg",
        "original_name": "Artify: magical realism"
    },
    "manga": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__manga.jpg",
        "original_name": "Artify: manga"
    },
    "melanin": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__melanin.jpg",
        "original_name": "Artify: melanin"
    },
    "messy": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__messy.jpg",
        "original_name": "Artify: messy"
    },
    "monochromatic": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__monochromatic.jpg",
        "original_name": "Artify: monochromatic"
    },
    "nature": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__nature.jpg",
        "original_name": "Artify: nature"
    },
    "photography": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__photography.jpg",
        "original_name": "Artify: photography"
    },
    "pop_art": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__pop_art.jpg",
        "original_name": "Artify: pop art"
    },
    "portrait": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__portrait.jpg",
        "original_name": "Artify: portrait"
    },
    "primitivism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__primitivism.jpg",
        "original_name": "Artify: primitivism"
    },
    "psychedelic": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__psychedelic.jpg",
        "original_name": "Artify: psychedelic"
    },
    "realism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__realism.jpg",
        "original_name": "Artify: realism"
    },
    "renaissance": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__renaissance.jpg",
        "original_name": "Artify: renaissance"
    },
    "romanticism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__romanticism.jpg",
        "original_name": "Artify: romanticism"
    },
    "scene": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__scene.jpg",
        "original_name": "Artify: scene"
    },
    "sci_fi": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__sci-fi.jpg",
        "original_name": "Artify: sci-fi"
    },
    "sculpture": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__sculpture.jpg",
        "original_name": "Artify: sculpture"
    },
    "seascape": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__seascape.jpg",
        "original_name": "Artify: seascape"
    },
    "space": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__space.jpg",
        "original_name": "Artify: space"
    },
    "stained_glass": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__stained_glass.jpg",
        "original_name": "Artify: stained glass"
    },
    "still_life": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__still_life.jpg",
        "original_name": "Artify: still life"
    },
    "storybook_realism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__storybook_realism.jpg",
        "original_name": "Artify: storybook realism"
    },
    "street_art": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__street_art.jpg",
        "original_name": "Artify: street art"
    },
    "streetscape": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__streetscape.jpg",
        "original_name": "Artify: streetscape"
    },
    "surrealism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__surrealism.jpg",
        "original_name": "Artify: surrealism"
    },
    "symbolism": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__symbolism.jpg",
        "original_name": "Artify: symbolism"
    },
    "textile": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__textile.jpg",
        "original_name": "Artify: textile"
    },
    "ukiyo_e": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__ukiyo-e.jpg",
        "original_name": "Artify: ukiyo-e"
    },
    "vibrant": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__vibrant.jpg",
        "original_name": "Artify: vibrant"
    },
    "watercolor": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__watercolor.jpg",
        "original_name": "Artify: watercolor"
    },
    "whimsical": {
        "positive": [
            "{prompt}"
        ],
        "negative": [],
        "thumbnail": "assets/style_thumbnails/Artify__whimsical.jpg",
        "original_name": "Artify: whimsical"
    }
}
