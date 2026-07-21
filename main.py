import pygame

from primiengine import Log, Assets, Render, Actors
from player import Player


def main():

    pygame.init()

    screen = pygame.display.set_mode(
        (800, 600)
    )

    Render.init(screen)
    Actors.init()

    log = Log.get("main")

    log.info("Engine starting")

    # Load immediately (blocking)
    Assets.load(
        "player",
        "assets/player.png"
    )

    # Spawn outside the loop
    Actors.spawn(
        Player,
        texture=Assets.get("player"),
        position=(400, 300),
        speed=250
    )

    clock = pygame.time.Clock()

    running = True

    while running:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

        Render.present()

        clock.tick(60)

    Actors.close()
    Render.close()
    Log.close()


if __name__ == "__main__":
    main()
