-- CreateTable
CREATE TABLE `Road` (
    `id` VARCHAR(191) NOT NULL,
    `jobId` VARCHAR(191) NOT NULL,
    `terrainId` VARCHAR(191) NOT NULL,
    `userId` VARCHAR(191) NOT NULL,
    `controlPoints` JSON NOT NULL,
    `blendFilePath` VARCHAR(191) NOT NULL,
    `previewPath` VARCHAR(191) NULL,
    `widthMeters` DOUBLE NOT NULL DEFAULT 1.6,
    `metadata` JSON NULL,
    `createdAt` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),

    UNIQUE INDEX `Road_jobId_key`(`jobId`),
    INDEX `Road_terrainId_idx`(`terrainId`),
    INDEX `Road_userId_idx`(`userId`),
    PRIMARY KEY (`id`)
) DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- AddForeignKey
ALTER TABLE `Road` ADD CONSTRAINT `Road_jobId_fkey` FOREIGN KEY (`jobId`) REFERENCES `Job`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE `Road` ADD CONSTRAINT `Road_terrainId_fkey` FOREIGN KEY (`terrainId`) REFERENCES `Terrain`(`id`) ON DELETE RESTRICT ON UPDATE CASCADE;
