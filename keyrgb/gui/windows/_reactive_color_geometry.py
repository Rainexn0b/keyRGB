from __future__ import annotations


def apply_centered_geometry(
    root: object,
    main_frame: object,
    *,
    compute_geometry_fn,
    apply_errors: tuple[type[BaseException], ...],
) -> None:
    try:
        root.update_idletasks()
        geometry = compute_geometry_fn(
            root,
            content_height_px=int(main_frame.winfo_reqheight()),
            content_width_px=int(main_frame.winfo_reqwidth()),
            footer_height_px=0,
            chrome_padding_px=44,
            default_w=629,
            default_h=940,
            screen_ratio_cap=0.95,
        )
        root.geometry(geometry)
    except apply_errors:
        return
