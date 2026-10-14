"""Editable sources and small operational settings for the tracker."""

MAX_ALERTS_PER_RUN = 10
REQUEST_TIMEOUT_SECONDS = 20
SEEN_FILE_PATH = "seen.json"
USER_AGENT = "QuantOpportunityTracker/2.0 (personal student opportunity monitor)"

# kind: html (listing cards/links), detail (one dedicated program page),
# events (several dated sections), greenhouse, or lever.
# Avoid broad corporate home pages: they produce generic, noisy matches.
MONITORED_SITES = [
    {"firm": "Arrowstreet Capital", "source": "Students", "url": "https://www.arrowstreetcapital.com/student-careers/", "kind": "html"},
    {"firm": "IMC", "source": "Student Programs", "url": "https://www.imc.com/us/careers/students-graduates/programs", "kind": "html"},
    {"firm": "IMC", "source": "Launchpad", "url": "https://www.imc.com/us/careers/students-graduates/programs/launchpad", "kind": "detail"},
    {"firm": "Citadel", "source": "Discover Citadel", "url": "https://www.citadel.com/careers/programs-and-events/discover-citadel/", "kind": "events"},
    {"firm": "Citadel", "source": "Programs and Events", "url": "https://www.citadel.com/careers/programs-and-events/", "kind": "html"},
    {"firm": "Optiver", "source": "Student Programs", "url": "https://www.optiver.com/join-us/students/programs/", "kind": "html"},
    {"firm": "Optiver", "source": "FutureFocus", "url": "https://www.optiver.com/join-us/students/programs/futurefocus/", "kind": "detail"},
    {"firm": "Optiver", "source": "Career Kickstarter", "url": "https://www.optiver.com/join-us/students/programs/career-kickstarter/", "kind": "detail"},
    {"firm": "Optiver", "source": "Internships", "url": "https://www.optiver.com/join-us/students/internships/", "kind": "html"},
    {"firm": "Jane Street", "source": "Programs and Events", "url": "https://www.janestreet.com/join-jane-street/programs-and-events/", "kind": "html"},
    {"firm": "Jane Street", "source": "FTTP", "url": "https://www.janestreet.com/join-jane-street/programs-and-events/fttp/", "kind": "detail"},
    {"firm": "Jane Street", "source": "Internships", "url": "https://www.janestreet.com/join-jane-street/internships/", "kind": "html"},
    {"firm": "Citadel Securities", "source": "Student Programs", "url": "https://www.citadelsecurities.com/careers/programs-and-events/", "kind": "html"},
    {"firm": "Two Sigma", "source": "Internships", "url": "https://www.twosigma.com/careers/internships/", "kind": "html"},
    {"firm": "Hudson River Trading", "source": "Students", "url": "https://www.hudsonrivertrading.com/student-opportunities/", "kind": "html"},
    {"firm": "D. E. Shaw", "source": "Internships", "url": "https://www.deshaw.com/careers/internships", "kind": "html"},
    {"firm": "SIG", "source": "Early Careers", "url": "https://careers.sig.com/early-careers", "kind": "html"},
    {"firm": "Tower Research", "source": "Internships", "url": "https://tower-research.com/internships/", "kind": "html"},
    {"firm": "Akuna Capital", "source": "Students", "url": "https://akunacapital.com/careers/students/", "kind": "html"},
    {"firm": "Jump Trading", "source": "Students", "url": "https://www.jumptrading.com/hr/students-new-grads", "kind": "html"},
    {"firm": "Point72", "source": "Students", "url": "https://careers.point72.com/students", "kind": "html"},
    {"firm": "Five Rings", "source": "Careers", "url": "https://fiverings.com/careers/", "kind": "html"},
    {"firm": "DRW", "source": "Open Roles", "url": "https://www.drw.com/work-at-drw/listings/", "kind": "html"},
    {"firm": "Flow Traders", "source": "Open Roles", "url": "https://www.flowtraders.com/careers/job-search", "kind": "html"},
    {"firm": "Squarepoint", "source": "Open Roles", "url": "https://www.squarepoint-capital.com/open-opportunities", "kind": "html"},
    {"firm": "WorldQuant", "source": "Open Roles", "url": "https://www.worldquant.com/career-listing/", "kind": "html"},
    {"firm": "Headlands Technologies", "source": "Careers", "url": "https://www.headlandstech.com/careers/", "kind": "html"},
    {"firm": "Schonfeld", "source": "Early Careers", "url": "https://www.schonfeld.com/careers/students-and-early-career/", "kind": "html"},
    {"firm": "Belvedere Trading", "source": "Open Roles", "url": "https://jobs.lever.co/belvederetrading", "kind": "lever", "board": "belvederetrading"},
    {"firm": "Bridgewater", "source": "Open Roles", "url": "https://job-boards.greenhouse.io/bridgewater89", "kind": "greenhouse", "board": "bridgewater89"},
    {"firm": "Radix Trading", "source": "Open Roles", "url": "https://job-boards.greenhouse.io/radixuniversity", "kind": "greenhouse", "board": "radixuniversity"},
    {"firm": "Maven Securities", "source": "Open Roles", "url": "https://job-boards.greenhouse.io/mavensecuritiesholdingltd", "kind": "greenhouse", "board": "mavensecuritiesholdingltd"},
]
