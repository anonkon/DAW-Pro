from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ChunkType = Literal["genre_target", "technique", "skill_pitfall"]


class KnowledgeChunk(BaseModel):
    """A retrievable piece of domain knowledge for the Gemini prompt.

    This is background context, not a fact about the user's own audio - the
    system prompt in chain.py tells the model to treat it that way. `source`
    cites where the claim came from (a URL, or an author/book/page citation
    for the excerpts in books/ - see docs/plan/05-ai-brain.md for the full
    reading list), or says "heuristic" for a threshold we chose ourselves
    rather than found in a reference (same transparency features.py already
    uses for ABSOLUTE_GATE_LUFS/KEY_CONFIDENCE_FLOOR).
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
    KnowledgeChunk(
        id="genre_metal",
        type="genre_target",
        title="Metal spectral-balance targets",
        body=(
            "Metal mixes commonly carry excessive energy below 40Hz - 'sonic "
            "sludge' that eats headroom without adding perceived weight - so "
            "a high-pass around 40-55Hz is standard practice. The 55-125Hz "
            "range is where the genre's real weight and impact actually live. "
            "Muddiness concentrates around 200-550Hz (typically centered near "
            "230Hz), and brightness/air for the master usually comes from a "
            "broad boost around 6-12kHz plus a lighter one around 10-14kHz."
        ),
        source=(
            "Mark Mynett, Metal Music Manual (mastering chapter), pp.45-49, "
            "excerpted in books/The_Art_of_Mastering_in_Music_-_Final.pdf"
        ),
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
            "sustain level rather than standing out above it. In mastering "
            "practice, limiter gain reduction is usually kept within 3-4dB "
            "at any single stage - splitting a bigger reduction across two "
            "gentler stages sounds more natural than one heavy one, and "
            "leaning on limiting for loudness rather than earlier mix "
            "decisions tends to flatten sharp transient energy into "
            "something blunter and more fatiguing."
        ),
        source=(
            "https://www.izotope.com/en/learn/what-is-crest-factor ; "
            "https://polarity.me/posts/polarity-music/2025-04-09-measure-compression-with-the-crest-factor/ ; "
            "https://mixanalytic.com/guides/dynamic-range-analysis ; "
            "mastering-chapter excerpts, The Art of Mastering in Music, "
            "pp.61-63, excerpted in books/The_Art_of_Mastering_in_Music_-_Final.pdf"
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
            "rather than boosting the ones that do. A useful diagnostic is "
            "applying a broad high-frequency boost across the whole mix "
            "midway through mixing - it often reveals a problem a dull-"
            "sounding mix was masking more clearly than the boost itself "
            "fixes anything. Reflexively high-passing every non-bass "
            "instrument 'because lows should only come from bass' is a "
            "common but usually unnecessary habit of its own."
        ),
        source=(
            "https://babyaud.io/blog/fix-a-muddy-mix ; "
            "https://www.izotope.com/en/learn/8-common-compression-mistakes-music-producers-make ; "
            "Wessel Oltheten, Mixing with Impact, pp.42, 44-45, excerpted in "
            "books/Mixing_Techniques_for_Audio_-_FINAL.pdf"
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
            "near-mono rather than processing it wide. Mid/Side (M/S) "
            "processing - splitting a stereo signal into Mid (L+R) and Side "
            "(L-R) and treating each independently - is the standard tool "
            "for this, and a correlation meter reading near zero or negative "
            "is a direct sign of poor mono compatibility worth checking "
            "before committing to a wide low end. The convention has a "
            "physical precedent too: vinyl cutting kept large low-frequency "
            "energy in the Mid channel because strong out-of-phase bass "
            "could push the cutting stylus out of the groove."
        ),
        source=(
            "https://www.masteringthemix.com/blogs/learn/how-to-add-width-to-bass-without-losing-mono-compatibility ; "
            "https://dowdenmusic.com/bass-in-mono/ ; "
            "https://www.sonible.com/blog/stereo-to-mono/ ; "
            "Wessel Oltheten, Mixing with Impact, pp.55-57, 62, excerpted in "
            "books/Mixing_Techniques_for_Audio_-_FINAL.pdf"
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
            "it's consistent (systematic offset) or scattered (random). One "
            "concrete way to keep a low end clear while still allowing "
            "rhythmic movement is treating kick and bass as a single "
            "monophonic line whose note onsets never overlap - trance and "
            "some commercial EDM conventionally place bass only on the "
            "off-beats against a kick on every downbeat, while techno and "
            "house allow busier bass patterns as long as the attacks stay "
            "separated from the kick's."
        ),
        source=(
            "https://beatkitchen.io/guides/electronic-music/01-genre-landscape/ ; "
            "https://strongmocha.com/creator-sound-design/midi-timing/ ; "
            "https://musicproductionwiki.com/articles/how-to-use-groove-and-swing-in-music.html ; "
            "Dennis DeSantis, Making Music: 74 Creative Strategies for "
            "Electronic Music Producers, 'Bass Lines and Kick Drums as a "
            "Single Composite,' pp.158-161, books/MakingMusic_DennisDeSantis.pdf"
        ),
    ),
    KnowledgeChunk(
        id="technique_transient_attack",
        type="technique",
        title="Transient attack character",
        body=(
            "Attack time - how quickly a sound's envelope rises to its peak "
            "after an onset - isn't inherently good or bad on its own. A "
            "slow attack from a compressor is sometimes chosen deliberately "
            "to let the initial transient through un-clamped and emphasize "
            "it, and a clearly-defined transient is generally what reads as "
            "impact and punch. The real risk sits at the other end: "
            "aggressive limiting or clipping used to chase loudness can "
            "smear or destroy a transient outright, which is a common way a "
            "mix loses punch even while measuring louder."
        ),
        source=(
            "game-audio sound-design chapter excerpts, Pro Techniques for "
            "Sound Design, pp.129-131, excerpted in "
            "books/Pro+Techniques+for+Sound+Design+.pdf"
        ),
    ),
    KnowledgeChunk(
        id="technique_thin_low_end",
        type="technique",
        title="Thin/small low end vs. a reference",
        body=(
            "A low end that reads as thin or small relative to a reference "
            "track is often caused by over-applying high-pass filters - a "
            "common habit is reflexively high-passing every non-bass "
            "instrument on the assumption that 'lows should only come from "
            "bass,' which strips low-frequency body from parts that "
            "actually needed some. Unless there's an audible problem "
            "(rumble, mud, phase issues), a smaller corrective shelf or bell "
            "move is usually enough - indiscriminate high-passing across a "
            "mix tends to make it progressively smaller and flatter rather "
            "than cleaner."
        ),
        source="Wessel Oltheten, Mixing with Impact, p.42, excerpted in books/Mixing_Techniques_for_Audio_-_FINAL.pdf",
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
            "A common beginner habit is reaching for heavy compression or a "
            "limiter on the master bus for 'glue' or extra loudness, which "
            "squashes the whole mix's dynamics at once rather than fixing "
            "the underlying arrangement or level-balance issue. Overusing "
            "limiting this way takes sharp, punchy transient energy and "
            "flattens it into something blunter and more fatiguing, "
            "sometimes with audible distortion in the upper-mids."
        ),
        source=(
            "https://babyaud.io/blog/fix-a-muddy-mix ; mastering-chapter "
            "excerpts, The Art of Mastering in Music, pp.61-63, excerpted in "
            "books/The_Art_of_Mastering_in_Music_-_Final.pdf"
        ),
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
        id="skill_beginner_hpf_default",
        type="skill_pitfall",
        title="Beginner pitfall: reflexive high-pass filtering",
        body=(
            "A common beginner habit is defaulting to a high-pass filter on "
            "every non-bass track as a blanket rule, rather than only where "
            "there's an actual audible problem in that range. Applied "
            "indiscriminately across many tracks, this steadily strips "
            "low-frequency body from the mix and can leave it sounding "
            "smaller and flatter than the mud it was meant to guard against."
        ),
        source="Wessel Oltheten, Mixing with Impact, p.42, excerpted in books/Mixing_Techniques_for_Audio_-_FINAL.pdf",
    ),
    KnowledgeChunk(
        id="skill_intermediate_mono_compat",
        type="skill_pitfall",
        title="Intermediate pitfall: stereo width without mono checks",
        body=(
            "Producers past the beginner stage often have decent gain "
            "staging but still push stereo-widening tools on the low end "
            "without watching a correlation meter, since the extra width "
            "sounds impressive in isolation and the resulting mono "
            "cancellation is easy to miss unless it's actively checked for."
        ),
        source=(
            "https://www.sonible.com/blog/stereo-to-mono/ ; Wessel Oltheten, "
            "Mixing with Impact, p.62, excerpted in "
            "books/Mixing_Techniques_for_Audio_-_FINAL.pdf"
        ),
    ),
]

ALL_CHUNKS: dict[str, KnowledgeChunk] = {
    chunk.id: chunk for chunk in [*GENRE_CHUNKS, *TECHNIQUE_CHUNKS, *SKILL_CHUNKS]
}
