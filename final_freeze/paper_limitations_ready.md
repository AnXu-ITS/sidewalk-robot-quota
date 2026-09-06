# Limitations (paper-ready)

1. **Simulation-derived references.** All quota references are simulation-derived
   (SUMO–JuPedSim). They are not real-world measured robot capacity, and no number
   in this work should be read as a real-world ground-truth capacity.

2. **Behavioral models.** The pedestrian and robot behavioral models may not
   capture all real interactions (e.g., negotiation, evasive behavior, group
   dynamics, weather, or obstacle clutter).

3. **Geometry coverage.** Unusual curved or complex sidewalk geometries can lie
   outside the applicability domain. The Amsterdam long-tail is evidence of this
   boundary, and it is handled by the baseline-feasibility guard and the
   out-of-domain fallback rather than by extending the law.

4. **Length effect unresolved.** The effect of sidewalk length was not identifiable
   under the current protocol (all cells 50 m; the simulator is length-insensitive
   by construction), so it remains an open question.

5. **Deployment dependence on offline qualification.** The baseline-feasibility
   status (`base_pass`) is a per-(cell, pedestrian-flow) simulation-derived flag.
   Depending on the deployment architecture, obtaining it may require offline
   sidewalk prequalification; the operational rule is therefore
   offline-qualification + online-closed-form, not a purely closed-form function
   of width and flow alone.

6. **External validation still required.** Real-world external validation is still
   required before any deployment claim. The current evaluation is held-out-city
   overprediction against simulation references only.
