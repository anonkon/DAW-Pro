from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ChunkType = Literal["genre_target", "technique", "skill_pitfall"]


class KnowledgeChunk(BaseModel):
    """A retrievable piece of domain knowledge for the Gemini prompt.

    This is background context, not a fact about the user's own audio - the
    system prompt in chain.py tells the model to treat it that way. `source`
    cites where the claim came from, or says "heuristic" for a threshold we
    chose ourselves rather than found in a reference (same transparency
    features.py already uses for ABSOLUTE_GATE_LUFS/KEY_CONFIDENCE_FLOOR).
    """

    id: str
    type: ChunkType
    title: str
    body: str
    source: str


# --- Genre targets ----------------------------------------------------------

GENRE_CHUNKS: list[KnowledgeChunk] = [
    KnowledgeChunk(
        id="genre_trap_hiphop",
        type="genre_target",
        title="Trap / modern hip-hop targets",
        body=(
            "Modern trap and hip-hop masters typically sit around -8 to -11 "
            "integrated LUFS with true peak at or below -1 dBTP - louder and "
            "denser than most other genres. Sub-bass energy (808s) is "
            "commonly concentrated around 20-50Hz, lower than older rap "
            "records which centered closer to 70Hz. The vocal needs to cut "
            "through that dense low end rather than compete with it."
        ),
        source=(
            "https://luvlang.studio/blog/how-loud-should-my-master-be ; "
            "https://beatstorapon.com/blog/rap-mastering-settings-2025-professional-targets-presets-and-platform-delivery-for-rap-trap-rb/ ; "
            "https://gearspace.com/board/mastering-forum/1248356-low-frequency-extension-modern-rap-records.html"
        ),
    ),
    KnowledgeChunk(
        id="genre_lofi_hiphop",
        type="genre_target",
        title="Lo-fi hip-hop targets",
        body=(
            "Lo-fi hip-hop is a more dynamic subgenre, commonly sitting "
            "around -12 to -14 integrated LUFS rather than being pushed loud. "
            "The characteristic sound deliberately lacks extreme highs and "
            "lows - a flattened top end and a controlled, not extended, low "
            "end - since the genre is going for a relaxed, calm character "
            "rather than maximum impact."
        ),
        source="https://www.masteringthemix.com/blogs/learn/how-to-make-lo-fi-hip-hop",
    ),
    KnowledgeChunk(
        id="genre_edm_electronic",
        type="genre_target",
        title="EDM / electronic targets",
        body=(
            "Electronic genres tolerate more loudness than most: commonly "
            "-10 to -6 integrated LUFS, with some tracks pushed beyond -6. "
            "True peak should still stay at or below -1 dBTP regardless of "
            "how loud the integrated level is pushed. Streaming platforms "
            "normalize loudness on playback, so mastering to the genre's "
            "expected density (not to a fixed -14 LUFS number) is normal "
            "practice here."
        ),
        source="https://www.edmprod.com/lufs/",
    ),
]

# --- Technique explanations, each keyed to a measurement trigger in
# retrieval.py -------------------------------------------------------------

TECHNIQUE_CHUNKS: list[KnowledgeChunk] = [
    KnowledgeChunk(
        id="technique_crest_factor",
        type="technique",
        title="Low crest factor / over-compression",
        body=(
            "Crest factor is the gap between peak and RMS level - a rough "
            "read on how much punch is left in a signal. Most well-produced "
            "electronic music sits around 6-10 dB of crest factor; below "
            "roughly 4 dB a track tends to read as flat and fatiguing, "
            "because the transients have been squashed down toward the "
            "sustain level rather than standing out above it. Once a source "
            "is already that flat, more compression won't add punch back - "
            "it can only flatten it further."
        ),
        source=(
            "https://www.izotope.com/en/learn/what-is-crest-factor ; "
            "https://polarity.me/posts/polarity-music/2025-04-09-measure-compression-with-the-crest-factor/ ; "
            "https://mixanalytic.com/guides/dynamic-range-analysis"
        ),
    ),
    KnowledgeChunk(
        id="technique_low_mid_mud",
        type="technique",
        title="Low-mid buildup ('mud')",
        body=(
            "Low-mid mud concentrates roughly 200-500Hz - the range that "
            "carries the warmth and body of most instruments at once. When "
            "several parts overlap there, the energy sums and the mix reads "
            "as thick and undefined rather than punchy. It's usually cured "
            "by cutting that range on the instruments that don't need it, "
            "rather than boosting the ones that do."
        ),
        source=(
            "https://babyaud.io/blog/fix-a-muddy-mix ; "
            "https://www.izotope.com/en/learn/8-common-compression-mistakes-music-producers-make"
        ),
    ),
    KnowledgeChunk(
        id="technique_stereo_bass_mono",
        type="technique",
        title="Wide stereo bass / mono compatibility",
        body=(
            "Human hearing can't localize very low frequencies, so widening "
            "the low end in stereo adds no perceptual width - what it adds "
            "is phase differences between left and right that partially "
            "cancel when the mix is summed to mono (phone speakers, "
            "Bluetooth speakers, and club systems with a single mono sub all "
            "do this). The usual fix is keeping bass content mono or "
            "near-mono rather than processing it wide."
        ),
        source=(
            "https://www.masteringthemix.com/blogs/learn/how-to-add-width-to-bass-without-losing-mono-compatibility ; "
            "https://dowdenmusic.com/bass-in-mono/ ; "
            "https://www.sonible.com/blog/stereo-to-mono/"
        ),
    ),
    KnowledgeChunk(
        id="technique_timing_swing",
        type="technique",
        title="Timing looseness: sloppy vs. genre swing",
        body=(
            "Timing tightness reads differently depending on genre. Tight, "
            "quantized timing is expected in electronic/techno; hip-hop and "
            "lo-fi commonly use intentional swing or microtiming as a "
            "genre feature, not a mistake - trap hi-hats in particular are "
            "often deliberately 1/16-quantized rolls rather than dead-on the "
            "grid. Low measured rhythmic cohesion is worth noting either way, "
            "but whether it reads as 'sloppy' or 'groovy' depends on whether "
            "it's consistent (systematic offset) or scattered (random)."
        ),
        source=(
            "https://beatkitchen.io/guides/electronic-music/01-genre-landscape/ ; "
            "https://strongmocha.com/creator-sound-design/midi-timing/ ; "
            "https://musicproductionwiki.com/articles/how-to-use-groove-and-swing-in-music.html"
        ),
    ),
]

# --- Skill-tier pitfalls, only surfaced when their paired technique trigger
# also fires (see retrieval.py) - otherwise they're generic advice with
# nothing to ground them in this analysis. ----------------------------------

SKILL_CHUNKS: list[KnowledgeChunk] = [
    KnowledgeChunk(
        id="skill_beginner_overcompression",
        type="skill_pitfall",
        title="Beginner pitfall: master-bus over-compression",
        body=(
            "A common beginner habit is reaching for heavy compression on "
            "the master bus for 'glue,' which instead squashes the whole "
            "mix's dynamics at once and reads as mud rather than punch."
        ),
        source="https://babyaud.io/blog/fix-a-muddy-mix",
    ),
    KnowledgeChunk(
        id="skill_beginner_low_mid_stacking",
        type="skill_pitfall",
        title="Beginner pitfall: unmanaged low-mid stacking",
        body=(
            "A common beginner habit is layering multiple instruments "
            "without carving space in the low-mids first, so warmth from "
            "several sources piles up in the same 200-500Hz range instead of "
            "each part having room."
        ),
        source="https://adrianmilea.com/how-to-fix-muddy-mix/",
    ),
    KnowledgeChunk(
        id="skill_intermediate_mono_compat",
        type="skill_pitfall",
        title="Intermediate pitfall: stereo width without mono checks",
        body=(
            "Producers past the beginner stage often have decent gain "
            "staging but still reach for stereo-widening on the low end "
            "without checking mono compatibility, since the wideness sounds "
            "impressive in stereo and the mono cancellation is easy to miss "
            "without deliberately checking for it."
        ),
        source="https://www.sonible.com/blog/stereo-to-mono/",
    ),
]

ALL_CHUNKS: dict[str, KnowledgeChunk] = {
    chunk.id: chunk for chunk in [*GENRE_CHUNKS, *TECHNIQUE_CHUNKS, *SKILL_CHUNKS]
}
